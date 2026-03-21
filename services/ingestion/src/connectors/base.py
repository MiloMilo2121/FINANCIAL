"""Abstract base class for all external API connectors.

Every connector must implement:
  - fetch() → list[dict]  — raw HTTP call to external API
  - normalize(raw) → MarketEvent  — map raw dict to canonical schema

The scheduler calls fetch() and normalize() polymorphically, then passes
results to the publisher. Rate limiting is handled at the connector level
by returning a RateLimiter via get_rate_limiter().
"""

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from financial_shared.logging import get_logger

logger = get_logger(__name__)

# Default exponential backoff with jitter (prevents retry storms)
DEFAULT_RETRY = retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    reraise=True,
)


class BaseConnector(ABC):
    """Abstract connector base class."""

    name: str  # Unique connector identifier; used as rate limit key

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch raw data from external API.

        Should handle pagination internally if needed.
        Returns a list of raw record dicts.
        """

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> Any:
        """Normalize a single raw record to a MarketEvent subclass."""

    async def fetch_and_normalize(self) -> list[Any]:
        """Fetch and normalize all records. Logs errors per-record."""
        raw_records = await self.fetch()
        events = []
        for raw in raw_records:
            try:
                event = self.normalize(raw)
                events.append(event)
            except Exception as exc:
                logger.warning(
                    "connector.normalize_failed",
                    connector=self.name,
                    error=str(exc),
                    raw_keys=list(raw.keys()) if isinstance(raw, dict) else None,
                )
        return events

    async def _get(self, url: str, params: dict | None = None, **kwargs) -> httpx.Response:
        """GET with exponential backoff on transient errors."""
        response = await self._http.get(url, params=params, **kwargs)
        response.raise_for_status()
        return response

    async def _post(self, url: str, json: dict | None = None, **kwargs) -> httpx.Response:
        """POST with exponential backoff on transient errors."""
        response = await self._http.post(url, json=json, **kwargs)
        response.raise_for_status()
        return response
