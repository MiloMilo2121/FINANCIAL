"""Redis connection factory with connection pooling."""

import redis.asyncio as aioredis
import redis as sync_redis
from redis.asyncio import Redis as AsyncRedis
from redis import Redis as SyncRedis


_async_pool: aioredis.ConnectionPool | None = None
_sync_pool: sync_redis.ConnectionPool | None = None


def get_async_redis(url: str, pool_size: int = 10) -> AsyncRedis:
    """Get an async Redis client backed by a connection pool."""
    global _async_pool
    if _async_pool is None:
        _async_pool = aioredis.ConnectionPool.from_url(
            url,
            max_connections=pool_size,
            decode_responses=True,
        )
    return aioredis.Redis(connection_pool=_async_pool)


def get_sync_redis(url: str, pool_size: int = 10) -> SyncRedis:
    """Get a synchronous Redis client (for Lua scripts in rate limiters)."""
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = sync_redis.ConnectionPool.from_url(
            url,
            max_connections=pool_size,
            decode_responses=True,
        )
    return sync_redis.Redis(connection_pool=_sync_pool)


async def close_async_pool() -> None:
    global _async_pool
    if _async_pool:
        await _async_pool.aclose()
        _async_pool = None
