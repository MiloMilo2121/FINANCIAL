"""Async SQLAlchemy engine factory."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_engine(
    url: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    echo: bool = False,
) -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            echo=echo,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def close_engine() -> None:
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
