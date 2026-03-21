"""Redis-based per-user API rate limiting at the gateway level.

Separate from the ingestion-layer rate limiting (which governs external API calls),
this layer limits individual user request rates to prevent API abuse.

Uses sliding window algorithm for precise per-user quota enforcement.
Keys: rate_limit:user:{user_id}:{window}

In production: replace with Cloud Armor WAF rules for L7 DDoS protection.
"""

import time
import uuid
from typing import Callable

from fastapi import HTTPException, Request
from redis import Redis

from financial_shared.logging import get_logger

logger = get_logger(__name__)

_LUA_USER_RATE_LIMIT = """
local key = KEYS[1]
local window_ms = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])
local request_id = ARGV[4]

local cutoff = now_ms - window_ms
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now_ms, request_id)
    redis.call('PEXPIRE', key, window_ms + 5000)
    return {1, limit - count - 1}
end
return {0, 0}
"""


class UserRateLimiter:
    """Per-user sliding window rate limiter."""

    def __init__(
        self,
        redis_client: Redis,
        requests_per_minute: int = 100,
    ) -> None:
        self._redis = redis_client
        self._requests_per_minute = requests_per_minute
        self._window_ms = 60_000
        self._script = redis_client.register_script(_LUA_USER_RATE_LIMIT)

    def check(self, user_id: str) -> tuple[bool, int]:
        """Check if user is within rate limit.

        Returns (allowed, remaining_requests).
        """
        key = f"rate_limit:user:{user_id}"
        now_ms = int(time.time() * 1000)
        request_id = f"{now_ms}-{uuid.uuid4().hex[:8]}"

        result = self._script(
            keys=[key],
            args=[self._window_ms, self._requests_per_minute, now_ms, request_id],
        )
        return bool(result[0]), int(result[1])

    def middleware(self, redis: Redis) -> Callable:
        """Returns a FastAPI middleware function."""
        limiter = self

        async def rate_limit_middleware(request: Request, call_next):
            # Extract user from JWT (already validated by auth middleware)
            user_id = getattr(request.state, "user_id", "anonymous")
            allowed, remaining = limiter.check(user_id)

            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": "60"},
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Limit"] = str(self._requests_per_minute)
            return response

        return rate_limit_middleware
