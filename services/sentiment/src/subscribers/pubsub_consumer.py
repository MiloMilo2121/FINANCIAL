"""Pub/Sub consumer for market events requiring sentiment analysis.

Subscribes to the 'market-events' topic and processes news-type events
by calling the Perplexity Sonar API for sentiment analysis.

Results are:
1. Published to the 'sentiment-events' Pub/Sub topic for ML consumption
2. Stored in Pinecone for semantic deduplication (avoid re-analyzing same news)
"""

import json
import threading
from typing import Any

from google.cloud.pubsub_v1.types import PubsubMessage

from financial_shared.pubsub import PubSubPublisher, PubSubSubscriber
from financial_shared.logging import get_logger
from financial_sentiment.perplexity.schemas import SentimentResult

logger = get_logger(__name__)


class SentimentEventConsumer:
    """Consumes market-events and produces sentiment-events."""

    def __init__(
        self,
        project_id: str,
        input_subscription: str,
        output_topic: str,
        sentiment_client,  # PerplexityClient
        pinecone_cache=None,
    ) -> None:
        self._project_id = project_id
        self._input_sub = input_subscription
        self._output_topic = output_topic
        self._client = sentiment_client
        self._cache = pinecone_cache

        self._subscriber = PubSubSubscriber(project_id)
        self._publisher = PubSubPublisher(project_id)

        self._streaming_future = None
        self._processed = 0
        self._errors = 0

    def _is_news_event(self, record: dict) -> bool:
        """Only process news-type events, not price ticks."""
        return record.get("asset_class") == "news"

    def _handle_message(self, message: PubsubMessage) -> None:
        """Process a single Pub/Sub message."""
        try:
            record = json.loads(message.data.decode("utf-8"))

            if not self._is_news_event(record):
                message.ack()
                return

            # Run async analysis in thread pool
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    self._client.analyze_gold_sentiment(
                        asset=record.get("asset", "XAU"),
                        context=record.get("metadata", {}).get("headline", ""),
                    )
                )
                self._publish_sentiment(record, result)
                self._processed += 1
                message.ack()
            finally:
                loop.close()

        except Exception as exc:
            self._errors += 1
            logger.error(
                "consumer.message_processing_failed",
                error=str(exc),
            )
            message.nack()  # Retry the message

    def _publish_sentiment(self, original_event: dict, result: SentimentResult) -> None:
        """Publish sentiment result to the output topic."""
        payload = {
            "original_event_id": original_event.get("event_id"),
            "asset": original_event.get("asset", "XAU"),
            "source_event": original_event.get("source"),
            "sentiment": result.model_dump(mode="json"),
            "ml_features": result.to_ml_features(),
        }
        self._publisher.publish(
            self._output_topic,
            payload,
            attributes={"type": "sentiment", "asset": original_event.get("asset", "XAU")},
        )
        logger.debug(
            "consumer.sentiment_published",
            asset=payload["asset"],
            score=result.asset_sentiment.sentiment_score,
        )

    def start(self) -> None:
        """Start streaming pull subscription."""
        self._subscriber.ensure_subscription(
            "market-events",
            self._input_sub,
        )
        self._publisher.ensure_topic(self._output_topic)

        self._streaming_future = self._subscriber.subscribe(
            self._input_sub,
            callback=self._handle_message,
        )
        logger.info(
            "consumer.started",
            subscription=self._input_sub,
            output_topic=self._output_topic,
        )

    def stop(self) -> None:
        if self._streaming_future:
            self._streaming_future.cancel()
        logger.info(
            "consumer.stopped",
            processed=self._processed,
            errors=self._errors,
        )

    def get_stats(self) -> dict:
        return {
            "processed": self._processed,
            "errors": self._errors,
            "error_rate": self._errors / max(1, self._processed + self._errors),
        }
