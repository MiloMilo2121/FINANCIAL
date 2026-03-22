"""CFTC Disaggregated COT Connector — Managed Money, Swap Dealers, Producers.

Uses the CFTC PRE (Public Reporting Environment) API — completely free, no key.
Endpoint: https://publicreporting.cftc.gov/api/

Fetches disaggregated COT data for COMEX:
  - Gold (Contract code: 088691)
  - Silver (Contract code: 084691)
  - Platinum (Contract code: 076651)
  - Palladium (Contract code: 075651)

Published indicators (8):
  COT_MM_net_gold       — Managed Money net positions (gold)
  COT_MM_net_silver     — Managed Money net positions (silver)
  COT_MM_net_platinum   — Managed Money net positions (platinum)
  COT_MM_net_palladium  — Managed Money net positions (palladium)
  COT_SD_net_gold       — Swap Dealers net positions (gold)
  COT_SD_net_silver     — Swap Dealers net positions (silver)
  COT_PM_net_gold       — Producer/Merchant net positions (gold)
  COT_MM_pct_OI_gold    — Managed Money % of Open Interest (gold)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from financial_shared.logging import get_logger
from .base import BaseConnector
from ..schemas.market_event import AssetClass, MacroEvent

logger = get_logger(__name__)

_PRE_BASE = "https://publicreporting.cftc.gov/api"
_RESOURCE = "HistoricalViewOiByFirmType"

# CFTC contract codes for precious metals
_CONTRACTS = {
    "088691": "gold",
    "084691": "silver",
    "076651": "platinum",
    "075651": "palladium",
}


class CFTCDisaggConnector(BaseConnector):
    """Fetches disaggregated CFTC COT data via the CFTC PRE public API."""

    source_name = "cftc_disagg"

    def _build_url(self, contract_code: str) -> str:
        # CFTC PRE OData-style endpoint: get latest 2 records ordered by date desc
        params = (
            f"$where=cftc_contract_market_code='{contract_code}'"
            f"&$order=report_date_as_yyyy_mm_dd DESC"
            f"&$limit=1"
        )
        return f"{_PRE_BASE}/{_RESOURCE}?{params}"

    async def fetch(self) -> dict[str, Any]:
        """Fetch all 4 metals, return combined raw data."""
        results: dict[str, Any] = {}
        for code, metal in _CONTRACTS.items():
            url = self._build_url(code)
            try:
                raw = await self._get(url)
                results[metal] = json.loads(raw)
            except Exception as exc:
                logger.warning("cftc_disagg: fetch failed for %s: %s", metal, exc)
                results[metal] = []
        return results

    def normalize(self, raw: dict[str, Any]) -> list[MacroEvent]:
        events: list[MacroEvent] = []
        now = datetime.now(timezone.utc)

        for metal, rows in raw.items():
            if not rows:
                continue
            row = rows[0]  # most recent record

            try:
                # Managed Money
                mm_long  = int(row.get("m_money_positions_long_all", 0) or 0)
                mm_short = int(row.get("m_money_positions_short_all", 0) or 0)
                mm_net   = mm_long - mm_short

                # Swap Dealers
                sd_long  = int(row.get("swap_positions_long_all", 0) or 0)
                sd_short = int(row.get("swap__positions_short_all", 0) or 0)
                sd_net   = sd_long - sd_short

                # Producer/Merchant/Processor/User
                pm_long  = int(row.get("prod_merc_positions_long_all", 0) or 0)
                pm_short = int(row.get("prod_merc_positions_short_all", 0) or 0)
                pm_net   = pm_long - pm_short

                # Open Interest
                oi = int(row.get("open_interest_all", 1) or 1)

                # Report date
                date_str = row.get("report_date_as_yyyy_mm_dd", "")
                try:
                    ts = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f").replace(
                        tzinfo=timezone.utc
                    )
                except Exception:
                    ts = now

            except Exception as exc:
                logger.warning("cftc_disagg: parse failed for %s: %s", metal, exc)
                continue

            def _pub(indicator: str, value: float) -> None:
                events.append(MacroEvent(
                    source=self.source_name,
                    indicator=indicator,
                    value=value,
                    currency="LOTS",
                    timestamp=ts,
                    freq="1w",
                    metadata={"metal": metal, "url": _PRE_BASE},
                ))

            _pub(f"COT_MM_net_{metal}", float(mm_net))

            if metal in ("gold", "silver"):
                _pub(f"COT_SD_net_{metal}", float(sd_net))

            if metal == "gold":
                _pub("COT_PM_net_gold", float(pm_net))
                mm_pct = float(mm_long / oi) if oi > 0 else 0.0
                _pub("COT_MM_pct_OI_gold", mm_pct)

        logger.info("cftc_disagg: published %d events", len(events))
        return events
