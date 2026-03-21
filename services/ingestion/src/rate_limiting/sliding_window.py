"""Redis Sliding Window Log rate limiter.

Uses a Redis Sorted Set (ZSET) to track the exact timestamp (millisecond
precision) of every request within the current window. Provides exact counts
with no approximation errors at window boundaries.

Used for high-value, strict-quota APIs:
- World Gold Council (daily/monthly limits)
- IMF / World Bank (strict rate limits)
- COMEX inventory data

Key schema: rate_limit:sliding_window:{connector_name}
  - ZSET with score = Unix timestamp (ms), member = unique request ID
"""

import time
import uuid
from dataclasses import dataclass

from redis import Redis

_LUA_SLIDING_WINDOW = """
local key = KEYS[1]
local window_ms = tonumber(ARGV[1])   -- window size in milliseconds
local limit = tonumber(ARGV[2])        -- max requests per window
local now_ms = tonumber(ARGV[3])       -- current time in milliseconds
local request_id = ARGV[4]

-- Remove expired entries (older than the window)
local cutoff = now_ms - window_ms
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

-- Count current entries in window
local count = redis.call('ZCARD', key)

local allowed = 0
if count < limit then
    -- Add current request with timestamp as score
    redis.call('ZADD', key, now_ms, request_id)
    allowed = 1
    count = count + 1
end

-- Set TTL to window size + buffer (prevent memory leak for idle keys)
redis.call('PEXPIRE', key, window_ms + 5000)

return {allowed, limit - count}
"""


@dataclass
class SlidingWindowConfig:
    window_seconds: float    # Window duration
    max_requests: int        # Maximum requests within window


class SlidingWindowLimiter:
    """Redis Sliding Window Log rate limiter.

    Provides exact request counting (no approximation) using Redis ZSET.
    Memory usage is proportional to the number of requests in the window.
    """

    def __init__(
        self,
        redis_client: Redis,
        connector_name: str,
        config: SlidingWindowConfig,
    ) -> None:
        self._redis = redis_client
        self._key = f"rate_limit:sliding_window:{connector_name}"
        self._config = config
        self._window_ms = int(config.window_seconds * 1000)
        self._script = redis_client.register_script(_LUA_SLIDING_WINDOW)

    def is_allowed(self) -> tuple[bool, int]:
        """Check if a request is allowed.

        Returns:
            (allowed, remaining_capacity)
        """
        now_ms = int(time.time() * 1000)
        request_id = f"{now_ms}-{uuid.uuid4().hex[:8]}"

        result = self._script(
            keys=[self._key],
            args=[
                self._window_ms,
                self._config.max_requests,
                now_ms,
                request_id,
            ],
        )
        allowed = bool(result[0])
        remaining = int(result[1])
        return allowed, remaining

    def get_current_count(self) -> int:
        """Get the current number of requests in the window (read-only)."""
        now_ms = int(time.time() * 1000)
        cutoff = now_ms - self._window_ms
        # Prune expired entries first
        self._redis.zremrangebyscore(self._key, "-inf", cutoff)
        return self._redis.zcard(self._key)

    def reset(self) -> None:
        """Reset the window (for testing only)."""
        self._redis.delete(self._key)
