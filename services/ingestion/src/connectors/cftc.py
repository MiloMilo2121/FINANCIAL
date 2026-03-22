"""CFTC Connector — Commitment of Traders (COT) Report for Gold.

The CFTC publishes weekly COT data as free public CSV files.
We use the legacy futures-and-options combined report:
  https://www.cftc.gov/dea/options/deahistfo_txt.htm

Gold contract: "GOLD - COMMODITY EXCHANGE INC."

Indicators produced:
  COT_commercials_net   — Commercial hedgers net position (longs - shorts)
  COT_speculators_net   — Non-commercial speculators net position
  COMEX_open_interest   — Total open interest

Reports are released every Friday for the prior Tuesday's positions.
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

_COT_URL = "https://www.cftc.gov/dea/options/deahistfo_txt.htm"

# Column indices in the legacy combined CSV (0-indexed after header)
# Header: Market_and_Exchange_Names, As_of_Date_in_Form_YYYY-MM-DD,
#         Open_Interest_All, ...
_GOLD_KEYWORD = "GOLD - COMMODITY EXCHANGE"


class CFTCConnector(BaseConnector):
    """Fetches CFTC COT gold positioning data."""

    name = "cftc"

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        super().__init__(http_client)

    async def fetch(self) -> list[dict[str, Any]]:
        try:
            resp = await self._get(_COT_URL)
            reader = csv.DictReader(io.StringIO(resp.text))
            rows = [r for r in reader if _GOLD_KEYWORD in r.get("Market_and_Exchange_Names", "").upper()]
            if not rows:
                logger.warning("cftc.gold_not_found in COT data")
                return []
            # Sort by date, take most recent
            rows_sorted = sorted(
                rows,
                key=lambda r: r.get("As_of_Date_in_Form_YYYY-MM-DD", ""),
                reverse=True,
            )
            return [rows_sorted[0]] if rows_sorted else []
        except Exception as exc:
            logger.warning("cftc.fetch_failed error=%s", exc)
            return []

    def normalize(self, raw: dict[str, Any]) -> MacroEvent:
        date_str = raw.get("As_of_Date_in_Form_YYYY-MM-DD", "")
        try:
            ts = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        def _int(key: str) -> float:
            v = raw.get(key, "0").replace(",", "").strip()
            try:
                return float(v) if v else 0.0
            except ValueError:
                return 0.0

        comm_longs  = _int("Comm_Positions_Long_All")
        comm_shorts = _int("Comm_Positions_Short_All")
        spec_longs  = _int("NonComm_Positions_Long_All")
        spec_shorts = _int("NonComm_Positions_Short_All")
        oi          = _int("Open_Interest_All")

        # Return three separate events by packing into a single record
        # then fan out in fetch_and_normalize override
        return MacroEvent(
            timestamp  = ts,
            source     = self.name,
            asset      = "XAU/COMEX/COT",
            asset_class= AssetClass.MACRO,
            price_usd  = oi,
            currency   = "LOTS",
            indicator  = "COMEX_open_interest",
            country    = "US",
            period     = date_str,
            metadata   = {
                "provider":           "cftc",
                "COT_commercials_net": comm_longs - comm_shorts,
                "COT_speculators_net": spec_longs - spec_shorts,
                "COMEX_open_interest": oi,
                "comm_longs":          comm_longs,
                "comm_shorts":         comm_shorts,
                "spec_longs":          spec_longs,
                "spec_shorts":         spec_shorts,
            },
        )

    async def fetch_and_normalize(self) -> list[MacroEvent]:
        """Override to fan out one raw row into three separate MacroEvents."""
        raw_records = await self.fetch()
        events: list[MacroEvent] = []
        for raw in raw_records:
            try:
                base_event = self.normalize(raw)
                ts         = base_event.timestamp
                period     = base_event.period
                meta_base  = {"provider": "cftc", "period": period}

                events.append(MacroEvent(
                    timestamp  = ts, source=self.name,
                    asset="XAU/COMEX/COT_COMMERCIALS",
                    asset_class=AssetClass.MACRO,
                    price_usd  = float(base_event.metadata["COT_commercials_net"]),
                    currency="LOTS", indicator="COT_commercials_net",
                    country="US", period=period, metadata=meta_base,
                ))
                events.append(MacroEvent(
                    timestamp  = ts, source=self.name,
                    asset="XAU/COMEX/COT_SPECULATORS",
                    asset_class=AssetClass.MACRO,
                    price_usd  = float(base_event.metadata["COT_speculators_net"]),
                    currency="LOTS", indicator="COT_speculators_net",
                    country="US", period=period, metadata=meta_base,
                ))
                events.append(MacroEvent(
                    timestamp  = ts, source=self.name,
                    asset="XAU/COMEX/OPEN_INTEREST",
                    asset_class=AssetClass.MACRO,
                    price_usd  = float(base_event.metadata["COMEX_open_interest"]),
                    currency="LOTS", indicator="COMEX_open_interest",
                    country="US", period=period, metadata=meta_base,
                ))
            except Exception as exc:
                logger.warning("cftc.normalize_failed error=%s", exc)
        return events
