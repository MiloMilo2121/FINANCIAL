"""Metals-API connector.

Provides real-time and historical precious metal rates with support for
150+ currencies, bid/ask spread data, and OHLCV historical data.

Serves as cross-validation source against MetalpriceAPI.

API docs: https://metals-api.com/documentation
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, OHLCVEvent

BASE_URL = "https://metals-api.com/api"

_METALS = ["XAU", "XAG", "XPT", "XPD"]


class MetalsAPIConnector(BaseConnector):
    """Fetches precious metal spot prices from Metals-API."""

    name = "metals_api"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(http_client)
        self._api_key = api_key

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch latest metal prices vs USD."""
        response = await self._get(
            f"{BASE_URL}/latest",
            params={
                "access_key": self._api_key,
                "base": "USD",
                "symbols": ",".join(_METALS),
            },
        )
        data = response.json()

        if not data.get("success"):
            raise Exception(f"Metals-API error: {data.get('error', {})}")

        rates = data.get("rates", {})
        timestamp = datetime.fromtimestamp(data.get("timestamp", 0), tz=timezone.utc)

        return [
            {
                "asset": metal,
                "timestamp": timestamp.isoformat(),
                "price_usd": 1.0 / rates[metal] if metal in rates and rates[metal] > 0 else None,
            }
            for metal in _METALS
            if metal in rates
        ]

    def normalize(self, raw: dict[str, Any]) -> OHLCVEvent:
        ts = datetime.fromisoformat(raw["timestamp"])
        return OHLCVEvent(
            timestamp=ts,
            source=self.name,
            asset=raw["asset"],
            asset_class=AssetClass.METAL,
            price_usd=raw.get("price_usd"),
            close=raw.get("price_usd"),
            currency="USD",
            interval="tick",
            metadata={"provider": "metals_api"},
        )
