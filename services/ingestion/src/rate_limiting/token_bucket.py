"""Redis Token Bucket rate limiter.

Uses a Lua script for atomicity — all operations (check + decrement + refill)
execute in a single atomic Redis transaction, eliminating race conditions in
distributed environments.

The Token Bucket algorithm is used for APIs that tolerate controlled bursts:
- Alpha Vantage (historical batch downloads)
- Metals-API (bulk commodity data)

Key schema: rate_limit:token_bucket:{connector_name}
  - tokens: current token count (float)
  - last_refill: Unix timestamp of last refill (float)
"""

import time
from dataclasses import dataclass

from redis import Redis

# Lua script: atomic check-and-consume
# Returns 1 if allowed, 0 if denied, along with remaining tokens
_LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])   -- tokens per second
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- Refill based on elapsed time
local elapsed = now - last_refill
local refilled = elapsed * refill_rate
tokens = math.min(capacity, tokens + refilled)
last_refill = now

local allowed = 0
local remaining = tokens
if tokens >= requested then
    tokens = tokens - requested
    remaining = tokens
    allowed = 1
end

redis.call('HSET', key, 'tokens', tokens, 'last_refill', last_refill)
redis.call('EXPIRE', key, 3600)  -- auto-expire idle buckets after 1 hour

return {allowed, remaining}
"""


@dataclass
class TokenBucketConfig:
    capacity: float          # Maximum tokens in bucket
    refill_rate: float       # Tokens added per second
    requested_tokens: float = 1.0  # Tokens consumed per request


class TokenBucketLimiter:
    """Redis-backed Token Bucket rate limiter.

    Thread-safe and process-safe via Lua atomicity.
    """

    def __init__(self, redis_client: Redis, connector_name: str, config: TokenBucketConfig) -> None:
        self._redis = redis_client
        self._key = f"rate_limit:token_bucket:{connector_name}"
        self._config = config
        self._script = redis_client.register_script(_LUA_TOKEN_BUCKET)

    def is_allowed(self) -> tuple[bool, float]:
        """Check if a request is allowed.

        Returns:
            (allowed, remaining_tokens)
        """
        result = self._script(
            keys=[self._key],
            args=[
                self._config.capacity,
                self._config.refill_rate,
                time.time(),
                self._config.requested_tokens,
            ],
        )
        allowed = bool(result[0])
        remaining = float(result[1])
        return allowed, remaining

    def wait_seconds(self) -> float:
        """Estimate seconds to wait before next token is available."""
        _, remaining = self.is_allowed.__wrapped__(self) if hasattr(self.is_allowed, '__wrapped__') else (False, 0.0)
        if remaining >= self._config.requested_tokens:
            return 0.0
        deficit = self._config.requested_tokens - remaining
        return deficit / self._config.refill_rate
