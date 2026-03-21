"""Pub/Sub publisher for market events.

Publishes normalized MarketEvent objects to the configured Pub/Sub topic.
Automatically uses the local emulator when PUBSUB_EMULATOR_HOST is set.
"""

import json
from typing import Any

from financial_shared.pubsub import PubSubPublisher
from financial_shared.logging import get_logger
from financial_ingestion.schemas.market_event import MarketEvent

logger = get_logger(__name__)


class MarketEventPublisher:
    """Publishes MarketEvent instances to Pub/Sub."""

    def __init__(self, project_id: str, topic_name: str) -> None:
        self._publisher = PubSubPublisher(project_id)
        self._topic_name = topic_name

    def publish_event(self, event: MarketEvent) -> str:
        """Publish a single MarketEvent. Returns the message ID."""
        payload = event.to_pubsub_payload()
        attributes = {
            "source": event.source,
            "asset": event.asset,
            "asset_class": event.asset_class.value,
        }
        future = self._publisher.publish(
            self._topic_name, payload, attributes=attributes
        )
        message_id = future.result(timeout=10)
        logger.debug(
            "publisher.event_published",
            message_id=message_id,
            source=event.source,
            asset=event.asset,
        )
        return message_id

    def publish_batch(self, events: list[MarketEvent]) -> list[str]:
        """Publish multiple events. Returns list of message IDs."""
        message_ids = []
        failed = 0
        for event in events:
            try:
                mid = self.publish_event(event)
                message_ids.append(mid)
            except Exception as exc:
                failed += 1
                logger.error(
                    "publisher.batch_event_failed",
                    source=event.source,
                    asset=event.asset,
                    error=str(exc),
                )
        if failed:
            logger.warning(
                "publisher.batch_partial_failure",
                total=len(events),
                published=len(message_ids),
                failed=failed,
            )
        return message_ids

    def ensure_topic(self) -> None:
        """Create the topic if it doesn't exist."""
        self._publisher.ensure_topic(self._topic_name)
