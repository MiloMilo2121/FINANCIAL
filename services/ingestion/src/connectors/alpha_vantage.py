"""Alpha Vantage connector.

Fetches OHLCV data for gold (XAU) and silver (XAG) spot prices,
plus technical indicators (RSI, MACD, Bollinger Bands).

Rate limit: 5 requests/minute (free), 75 requests/minute (premium).
Uses Token Bucket to allow burst downloads of historical data.

API docs: https://www.alphavantage.co/documentation/
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, OHLCVEvent

BASE_URL = "https://www.alphavantage.co/query"

# Forex symbol for gold vs USD
_ASSET_MAP = {
    "XAU": ("from_currency", "XAU", "to_currency", "USD"),
    "XAG": ("from_currency", "XAG", "to_currency", "USD"),
}


class AlphaVantageConnector(BaseConnector):
    """Fetches daily OHLCV for precious metals from Alpha Vantage."""

    name = "alpha_vantage"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(http_client)
        self._api_key = api_key

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch daily OHLCV for XAU/USD and XAG/USD."""
        records = []
        for asset, (fk, fv, tk, tv) in _ASSET_MAP.items():
            params = {
                "function": "FX_DAILY",
                fk: fv,
                tk: tv,
                "outputsize": "compact",  # last 100 data points
                "apikey": self._api_key,
            }
            response = await self._get(BASE_URL, params=params)
            data = response.json()

            if "Time Series FX (Daily)" not in data:
                # Handle rate limit or error response
                if "Note" in data or "Information" in data:
                    msg = data.get("Note") or data.get("Information", "Unknown error")
                    raise Exception(f"Alpha Vantage rate limited: {msg}")
                continue

            time_series = data["Time Series FX (Daily)"]
            for date_str, ohlcv in time_series.items():
                records.append({
                    "asset": asset,
                    "date": date_str,
                    "open": ohlcv["1. open"],
                    "high": ohlcv["2. high"],
                    "low": ohlcv["3. low"],
                    "close": ohlcv["4. close"],
                    "volume": None,  # FX endpoint doesn't provide volume
                })
        return records

    def normalize(self, raw: dict[str, Any]) -> OHLCVEvent:
        ts = datetime.strptime(raw["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return OHLCVEvent(
            timestamp=ts,
            source=self.name,
            asset=raw["asset"],
            asset_class=AssetClass.METAL,
            open=float(raw["open"]) if raw.get("open") else None,
            high=float(raw["high"]) if raw.get("high") else None,
            low=float(raw["low"]) if raw.get("low") else None,
            close=float(raw["close"]) if raw.get("close") else None,
            price_usd=float(raw["close"]) if raw.get("close") else None,
            volume=float(raw["volume"]) if raw.get("volume") else None,
            currency="USD",
            interval="1d",
            metadata={"provider": "alpha_vantage"},
        )
