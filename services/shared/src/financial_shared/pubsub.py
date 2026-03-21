"""Google Cloud Pub/Sub client wrapper with emulator support.

When PUBSUB_EMULATOR_HOST is set in the environment, the client
automatically connects to the local emulator — no code changes needed
for production where the variable is absent.
"""

import json
import os
from collections.abc import Callable
from concurrent.futures import Future
from typing import Any

from google.cloud import pubsub_v1
from google.pubsub_v1.types import PubsubMessage

from financial_shared.logging import get_logger

logger = get_logger(__name__)


def _is_emulator() -> bool:
    return bool(os.environ.get("PUBSUB_EMULATOR_HOST"))


class PubSubPublisher:
    """Async-friendly Pub/Sub publisher."""

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._client = pubsub_v1.PublisherClient()

    def topic_path(self, topic_name: str) -> str:
        return self._client.topic_path(self._project_id, topic_name)

    def publish(
        self,
        topic_name: str,
        data: dict[str, Any],
        attributes: dict[str, str] | None = None,
    ) -> Future:
        """Publish a JSON-serializable dict to a Pub/Sub topic.

        Returns a Future that resolves to the published message ID.
        """
        topic = self.topic_path(topic_name)
        encoded = json.dumps(data, default=str).encode("utf-8")
        attrs = attributes or {}
        future = self._client.publish(topic, encoded, **attrs)
        logger.debug(
            "pubsub.publish",
            topic=topic_name,
            emulator=_is_emulator(),
        )
        return future

    def ensure_topic(self, topic_name: str) -> None:
        """Create topic if it does not exist (idempotent)."""
        topic = self.topic_path(topic_name)
        try:
            self._client.create_topic(request={"name": topic})
            logger.info("pubsub.topic_created", topic=topic_name)
        except Exception as exc:
            # AlreadyExists is acceptable
            if "AlreadyExists" not in str(exc) and "409" not in str(exc):
                raise

    def close(self) -> None:
        self._client.transport.close()


class PubSubSubscriber:
    """Streaming pull subscriber."""

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._client = pubsub_v1.SubscriberClient()

    def subscription_path(self, subscription_name: str) -> str:
        return self._client.subscription_path(self._project_id, subscription_name)

    def ensure_subscription(self, topic_name: str, subscription_name: str) -> None:
        """Create subscription if it does not exist (idempotent)."""
        publisher = pubsub_v1.PublisherClient()
        topic = publisher.topic_path(self._project_id, topic_name)
        subscription = self.subscription_path(subscription_name)
        try:
            self._client.create_subscription(
                request={"name": subscription, "topic": topic}
            )
            logger.info(
                "pubsub.subscription_created",
                subscription=subscription_name,
                topic=topic_name,
            )
        except Exception as exc:
            if "AlreadyExists" not in str(exc) and "409" not in str(exc):
                raise

    def subscribe(
        self,
        subscription_name: str,
        callback: Callable[[PubsubMessage], None],
        max_messages: int = 100,
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        """Start streaming pull subscription.

        The callback receives a google.cloud.pubsub_v1.types.PubsubMessage.
        Call message.ack() inside callback when processing is complete.
        """
        subscription = self.subscription_path(subscription_name)
        flow_control = pubsub_v1.types.FlowControl(max_messages=max_messages)
        future = self._client.subscribe(
            subscription, callback=callback, flow_control=flow_control
        )
        logger.info(
            "pubsub.subscriber_started",
            subscription=subscription_name,
            emulator=_is_emulator(),
        )
        return future

    def close(self) -> None:
        self._client.transport.close()
