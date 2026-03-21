"""APScheduler-based polling scheduler for all data connectors.

Each connector is polled at its configured interval. The scheduler:
1. Runs fetch_and_normalize() on the connector
2. Applies rate limiting (blocks or skips if limit exceeded)
3. Publishes results to Pub/Sub via MarketEventPublisher

Exponential backoff with jitter is applied on connector failures to
prevent retry storms against external APIs.
"""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from financial_shared.logging import get_logger
from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.pipeline.publisher import MarketEventPublisher
from financial_ingestion.rate_limiting.token_bucket import TokenBucketConfig, TokenBucketLimiter
from financial_ingestion.rate_limiting.sliding_window import SlidingWindowConfig, SlidingWindowLimiter

logger = get_logger(__name__)


@dataclass
class ConnectorScheduleConfig:
    connector: BaseConnector
    interval_seconds: int
    rate_limiter: TokenBucketLimiter | SlidingWindowLimiter | None = None
    max_retries: int = 3


class IngestionScheduler:
    """Orchestrates polling of all registered connectors."""

    def __init__(self, publisher: MarketEventPublisher) -> None:
        self._publisher = publisher
        self._scheduler = AsyncIOScheduler()
        self._configs: list[ConnectorScheduleConfig] = []

    def register(self, config: ConnectorScheduleConfig) -> None:
        """Register a connector for scheduled polling."""
        self._configs.append(config)
        self._scheduler.add_job(
            self._poll_connector,
            trigger=IntervalTrigger(seconds=config.interval_seconds),
            args=[config],
            id=config.connector.name,
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info(
            "scheduler.connector_registered",
            connector=config.connector.name,
            interval_seconds=config.interval_seconds,
        )

    async def _poll_connector(self, config: ConnectorScheduleConfig) -> None:
        """Execute a single connector poll cycle."""
        connector = config.connector

        # Check rate limit
        if config.rate_limiter is not None:
            allowed, remaining = config.rate_limiter.is_allowed()
            if not allowed:
                logger.debug(
                    "scheduler.rate_limited",
                    connector=connector.name,
                    remaining=remaining,
                )
                return

        # Fetch with exponential backoff
        for attempt in range(1, config.max_retries + 1):
            try:
                events = await connector.fetch_and_normalize()
                if events:
                    published = self._publisher.publish_batch(events)
                    logger.info(
                        "scheduler.poll_success",
                        connector=connector.name,
                        events_fetched=len(events),
                        events_published=len(published),
                    )
                return
            except Exception as exc:
                wait_seconds = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "scheduler.poll_failed",
                    connector=connector.name,
                    attempt=attempt,
                    max_retries=config.max_retries,
                    wait_seconds=round(wait_seconds, 2),
                    error=str(exc),
                )
                if attempt < config.max_retries:
                    await asyncio.sleep(wait_seconds)
                else:
                    logger.error(
                        "scheduler.poll_exhausted",
                        connector=connector.name,
                        error=str(exc),
                    )

    def start(self) -> None:
        self._scheduler.start()
        logger.info("scheduler.started", connector_count=len(self._configs))

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")
