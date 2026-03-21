"""Marketstack connector.

Provides OHLCV data for gold mining equities (GLD ETF, GOLD, NEM, AEM)
and global market indices correlated with precious metals (DXY proxy, SPX).

Rate limit: 100 requests/month (free tier).

API docs: https://marketstack.com/documentation
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, OHLCVEvent

BASE_URL = "http://api.marketstack.com/v1"

# Gold-correlated equities and ETFs
_SYMBOLS = ["GLD", "GOLD", "NEM", "AEM", "WPM", "FNV"]


class MarketstackConnector(BaseConnector):
    """Fetches OHLCV for gold mining equities from Marketstack."""

    name = "marketstack"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(http_client)
        self._api_key = api_key

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch end-of-day OHLCV for gold-correlated equities."""
        response = await self._get(
            f"{BASE_URL}/eod/latest",
            params={
                "access_key": self._api_key,
                "symbols": ",".join(_SYMBOLS),
                "limit": len(_SYMBOLS),
            },
        )
        data = response.json()

        if "error" in data:
            raise Exception(f"Marketstack error: {data['error']}")

        return data.get("data", [])

    def normalize(self, raw: dict[str, Any]) -> OHLCVEvent:
        ts_str = raw.get("date", raw.get("exchange_open", ""))
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.now(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        return OHLCVEvent(
            timestamp=ts,
            source=self.name,
            asset=raw.get("symbol", "UNKNOWN"),
            asset_class=AssetClass.EQUITY,
            open=raw.get("open"),
            high=raw.get("high"),
            low=raw.get("low"),
            close=raw.get("close"),
            price_usd=raw.get("close"),
            volume=raw.get("volume"),
            currency="USD",
            interval="1d",
            metadata={
                "provider": "marketstack",
                "exchange": raw.get("exchange"),
                "adj_close": raw.get("adj_close"),
            },
        )
