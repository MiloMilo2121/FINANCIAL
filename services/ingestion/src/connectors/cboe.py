"""CBOE Connector — VIX and VVIX volatility indices.

Both datasets are available as free public CSV downloads:
  VIX:  https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
  VVIX: https://cdn.cboe.com/api/global/us_indices/daily_prices/VVIX_History.csv

No API key required. The CSV endpoints are refreshed daily after market close.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

import httpx

from financial_shared.logging import get_logger
from .base import BaseConnector
from ..schemas.market_event import AssetClass, MacroEvent

logger = get_logger(__name__)

_CBOE_BASE = "https://cdn.cboe.com/api/global/us_indices/daily_prices"

_INDICES = {
    "VIX":  "VIX_index",
    "VVIX": "VVIX_index",
}


class CBOEConnector(BaseConnector):
    """Fetches VIX and VVIX from CBOE public CSV endpoints."""

    name = "cboe"

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        super().__init__(http_client)

    async def fetch(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for index_symbol, indicator_name in _INDICES.items():
            url = f"{_CBOE_BASE}/{index_symbol}_History.csv"
            try:
                resp = await self._get(url)
                rows = list(csv.reader(io.StringIO(resp.text)))
                if len(rows) < 2:
                    logger.warning("cboe.empty_response index=%s", index_symbol)
                    continue
                header = [h.strip().upper() for h in rows[0]]
                # Determine column indices (CBOE format: DATE, OPEN, HIGH, LOW, CLOSE)
                date_col  = next((i for i, h in enumerate(header) if "DATE" in h), 0)
                close_col = next((i for i, h in enumerate(header) if "CLOSE" in h), 4)
                # Last non-empty data row
                for row in reversed(rows[1:]):
                    if len(row) > close_col and row[close_col].strip():
                        try:
                            close_val = float(row[close_col].strip())
                            date_val  = row[date_col].strip()
                            records.append({
                                "symbol":    index_symbol,
                                "indicator": indicator_name,
                                "close":     close_val,
                                "date":      date_val,
                            })
                            break
                        except (ValueError, IndexError):
                            continue
            except Exception as exc:
                logger.warning("cboe.fetch_failed index=%s error=%s", index_symbol, exc)
        return records

    def normalize(self, raw: dict[str, Any]) -> MacroEvent:
        # Parse date: CBOE uses MM/DD/YYYY or YYYY-MM-DD
        date_str = raw["date"]
        try:
            if "/" in date_str:
                ts = datetime.strptime(date_str, "%m/%d/%Y").replace(tzinfo=timezone.utc)
            else:
                ts = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        return MacroEvent(
            timestamp  = ts,
            source     = self.name,
            asset      = f"VOLATILITY/{raw['symbol']}",
            asset_class= AssetClass.MACRO,
            price_usd  = float(raw["close"]),
            currency   = "INDEX",
            indicator  = raw["indicator"],
            country    = "US",
            period     = raw["date"],
            metadata   = {"provider": "cboe", "symbol": raw["symbol"]},
        )
