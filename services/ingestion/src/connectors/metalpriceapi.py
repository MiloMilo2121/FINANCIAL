"""MetalpriceAPI connector.

Provides real-time and historical spot prices for gold, silver, platinum,
palladium in 150+ currencies. Supports bid/ask spread data.

Rate limit: 100 requests/month (free), higher tiers available.
Uses Sliding Window Log for exact quota compliance.

API docs: https://metalpriceapi.com/documentation
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, OHLCVEvent

BASE_URL = "https://api.metalpriceapi.com/v1"

_METALS = ["XAU", "XAG", "XPT", "XPD"]  # Gold, Silver, Platinum, Palladium


class MetalpriceAPIConnector(BaseConnector):
    """Fetches real-time precious metal spot prices from MetalpriceAPI."""

    name = "metalpriceapi"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(http_client)
        self._api_key = api_key

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch latest spot prices for all precious metals vs USD."""
        response = await self._get(
            f"{BASE_URL}/latest",
            params={
                "api_key": self._api_key,
                "base": "USD",
                "currencies": ",".join(_METALS),
            },
        )
        data = response.json()

        if not data.get("success"):
            raise Exception(f"MetalpriceAPI error: {data.get('error', {})}")

        rates = data.get("rates", {})
        timestamp = datetime.fromtimestamp(data["timestamp"], tz=timezone.utc)

        return [
            {
                "asset": metal,
                "timestamp": timestamp.isoformat(),
                # API returns how many units of metal per 1 USD; invert for USD/oz
                "price_usd": 1.0 / rates[metal] if metal in rates and rates[metal] > 0 else None,
                "base": data.get("base", "USD"),
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
            metadata={"provider": "metalpriceapi", "base": raw.get("base", "USD")},
        )
