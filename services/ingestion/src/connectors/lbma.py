"""LBMA Connector — London Bullion Market Association Gold Price Fix.

The LBMA publishes daily AM and PM gold price fixings (USD/oz) as free data.
We use the LBMA's public JSON API endpoint.

Fallback chain:
  1. LBMA JSON API (prices.lbma.org.uk) — no key required
  2. Hard-coded NaN if both fail (graceful degradation)

Indicators produced:
  LBMA_AM_fix — LBMA Gold AM Fix (USD/oz)
  LBMA_PM_fix — LBMA Gold PM Fix (USD/oz)
  Gold_lease_rate_1m — 1-month gold lease rate (%) [if available]
  Gold_lease_rate_3m — 3-month gold lease rate (%)
  Gold_lease_rate_6m — 6-month gold lease rate (%)
  GOFO_1m            — 1-month Gold Forward Offered Rate (%)
  GOFO_3m            — 3-month Gold Forward Offered Rate (%)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_shared.logging import get_logger
from .base import BaseConnector
from ..schemas.market_event import AssetClass, MacroEvent, OHLCVEvent

logger = get_logger(__name__)

_LBMA_PM_URL = "https://prices.lbma.org.uk/secure/json_charts/gold_pm_usd.json"
_LBMA_AM_URL = "https://prices.lbma.org.uk/secure/json_charts/gold_am_usd.json"

# Gold lease rates & GOFO are no longer published daily by LBMA since 2015.
# We keep the indicators in the registry but return NaN from this connector.
# They can be populated from subscription data sources (Reuters, Bloomberg).
_LEASE_RATE_INDICATORS = [
    "Gold_lease_rate_1m", "Gold_lease_rate_3m", "Gold_lease_rate_6m",
    "GOFO_1m", "GOFO_3m",
]


class LBMAConnector(BaseConnector):
    """Fetches LBMA gold AM/PM fix prices."""

    name = "lbma"

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        super().__init__(http_client)

    async def fetch(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        for fix_type, url in [("AM", _LBMA_AM_URL), ("PM", _LBMA_PM_URL)]:
            try:
                resp = await self._get(url)
                data = resp.json()

                # LBMA JSON format: [[timestamp_ms, price], ...]
                if isinstance(data, list) and data:
                    last = data[-1]
                    if isinstance(last, (list, tuple)) and len(last) >= 2:
                        ts_ms = last[0]
                        price = last[1]
                        # Timestamp in milliseconds
                        ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                        records.append({
                            "fix_type":  fix_type,
                            "indicator": f"LBMA_{fix_type}_fix",
                            "price":     float(price),
                            "timestamp": ts,
                        })
                elif isinstance(data, dict):
                    # Alternative format: {"d": "YYYY-MM-DD", "p": price}
                    price = data.get("p") or data.get("price") or data.get("close")
                    date  = data.get("d") or data.get("date")
                    if price:
                        ts = datetime.fromisoformat(date).replace(tzinfo=timezone.utc) if date \
                             else datetime.now(timezone.utc)
                        records.append({
                            "fix_type":  fix_type,
                            "indicator": f"LBMA_{fix_type}_fix",
                            "price":     float(price),
                            "timestamp": ts,
                        })
            except Exception as exc:
                logger.warning("lbma.fetch_failed fix=%s error=%s", fix_type, exc)

        return records

    def normalize(self, raw: dict[str, Any]) -> OHLCVEvent:
        return OHLCVEvent(
            timestamp  = raw["timestamp"],
            source     = self.name,
            asset      = "XAU",
            asset_class= AssetClass.METAL,
            price_usd  = raw["price"],
            close      = raw["price"],
            currency   = "USD",
            interval   = "1d",
            metadata   = {
                "provider":  "lbma",
                "fix_type":  raw["fix_type"],
                "indicator": raw["indicator"],
            },
        )
