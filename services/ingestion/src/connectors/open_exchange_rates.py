"""Open Exchange Rates connector.

Normalizes all world currencies to USD to eliminate FX risk in commodity
price analysis. Provides hourly updates for 170+ currencies.

API docs: https://openexchangerates.org/api/docs
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, MarketEvent

BASE_URL = "https://openexchangerates.org/api"


class OpenExchangeRatesConnector(BaseConnector):
    """Fetches FX rates relative to USD for currency normalization."""

    name = "open_exchange_rates"

    def __init__(self, http_client: httpx.AsyncClient, app_id: str) -> None:
        super().__init__(http_client)
        self._app_id = app_id

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch latest rates for all currencies vs USD."""
        response = await self._get(
            f"{BASE_URL}/latest.json",
            params={"app_id": self._app_id, "base": "USD"},
        )
        data = response.json()

        if "error" in data:
            raise Exception(f"OpenExchangeRates error: {data['error']}")

        ts = datetime.fromtimestamp(data["timestamp"], tz=timezone.utc)
        rates = data.get("rates", {})

        return [
            {"currency": currency, "rate_vs_usd": rate, "timestamp": ts.isoformat()}
            for currency, rate in rates.items()
        ]

    def normalize(self, raw: dict[str, Any]) -> MarketEvent:
        ts = datetime.fromisoformat(raw["timestamp"])
        return MarketEvent(
            timestamp=ts,
            source=self.name,
            asset=f"USD/{raw['currency']}",
            asset_class=AssetClass.FX,
            price_usd=raw.get("rate_vs_usd"),
            currency="USD",
            metadata={"provider": "open_exchange_rates", "pair": f"USD/{raw['currency']}"},
        )
