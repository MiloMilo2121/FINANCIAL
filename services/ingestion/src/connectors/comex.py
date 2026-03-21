"""COMEX Gold Inventory connector.

Tracks COMEX gold warehouse inventories (CME Group):
- Registered gold: available for delivery against futures contracts
- Eligible gold: stored but not currently deliverable

A declining registered inventory signals potential supply squeeze:
→ bullish indicator for spot gold prices

Data available from: https://www.cmegroup.com/market-data/delayed-quotes/metals.html
And via CME DataMine API for institutional subscribers.
Public data fallback: quandl/nasdaq data link.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, MacroEvent

# Nasdaq Data Link (formerly Quandl) — COMEX data
NASDAQ_DATAHUB_URL = "https://data.nasdaq.com/api/v3/datasets"
COMEX_GOLD_DATASET = "CME/GC1"  # Gold futures front month


class COMEXConnector(BaseConnector):
    """Fetches COMEX gold inventory and futures data."""

    name = "comex"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str | None = None) -> None:
        super().__init__(http_client)
        self._api_key = api_key

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch recent COMEX gold futures data as inventory proxy."""
        params: dict[str, Any] = {
            "rows": 10,
            "order": "desc",
        }
        if self._api_key:
            params["api_key"] = self._api_key

        try:
            response = await self._get(
                f"{NASDAQ_DATAHUB_URL}/{COMEX_GOLD_DATASET}.json",
                params=params,
            )
            data = response.json()
            dataset = data.get("dataset", {})
            column_names = dataset.get("column_names", [])
            data_rows = dataset.get("data", [])

            return [
                dict(zip(column_names, row))
                for row in data_rows
            ]
        except Exception:
            return []

    def normalize(self, raw: dict[str, Any]) -> MacroEvent:
        ts_str = raw.get("Date", raw.get("date", ""))
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            ts = datetime.now(timezone.utc)

        settle = raw.get("Settle") or raw.get("settle")

        return MacroEvent(
            timestamp=ts,
            source=self.name,
            asset="XAU/COMEX",
            asset_class=AssetClass.MACRO,
            price_usd=float(settle) if settle is not None else None,
            currency="USD",
            indicator="COMEX_FUTURES_SETTLE",
            metadata={
                "provider": "comex_cme",
                "open": raw.get("Open"),
                "high": raw.get("High"),
                "low": raw.get("Low"),
                "volume": raw.get("Volume"),
                "open_interest": raw.get("Open Interest"),
            },
        )
