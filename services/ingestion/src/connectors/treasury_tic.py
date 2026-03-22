"""Treasury TIC Connector — Foreign Holdings of US Treasury Securities.

Free, no API key. Published monthly by US Treasury.
URL: https://ticdata.treasury.gov/Publish/mfh.txt

Indicators published:
  TIC_foreign_official_total  — Total foreign official Treasury holdings ($ billions)
  TIC_china_holdings          — China Treasury holdings ($ billions)
  TIC_japan_holdings          — Japan Treasury holdings ($ billions)
  TIC_opec_holdings           — OPEC countries Treasury holdings ($ billions)
  TIC_grand_total             — Grand total all foreign holders ($ billions)
  TIC_top10_share             — Top-10 country share of total (0-1)
  TIC_china_share             — China's share of grand total (0-1)
  TIC_japan_share             — Japan's share of grand total (0-1)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from financial_shared.logging import get_logger
from .base import BaseConnector
from ..schemas.market_event import AssetClass, MacroEvent

logger = get_logger(__name__)

_TIC_URL = "https://ticdata.treasury.gov/Publish/mfh.txt"


class TreasuryTICConnector(BaseConnector):
    """Fetches US Treasury TIC data on foreign official holdings."""

    source_name = "treasury_tic"

    async def fetch(self) -> str:
        return await self._get(_TIC_URL)

    def normalize(self, raw: str) -> list[MacroEvent]:
        """Parse TIC mfh.txt fixed-width format.

        The file has a header section followed by country rows like:
          CHINA, MAINLAND      1,089.4    1,089.4    ...
          JAPAN                1,068.1    1,068.1    ...
        """
        events: list[MacroEvent] = []
        now = datetime.now(timezone.utc)

        holdings: dict[str, float] = {}
        lines = raw.splitlines()

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Match country lines: country name + numeric values
            # Format: "COUNTRY NAME     value1  value2 ..."
            m = re.match(
                r"^([A-Z][A-Z ,\.]+?)\s{2,}([\d,]+\.?\d*)\s", line_stripped
            )
            if not m:
                continue

            country = m.group(1).strip().upper()
            try:
                value = float(m.group(2).replace(",", ""))
            except ValueError:
                continue

            # Map to known indicator names
            if "CHINA" in country and "MAINLAND" in country:
                holdings["TIC_china_holdings"] = value
            elif "JAPAN" in country:
                holdings["TIC_japan_holdings"] = value
            elif "GRAND TOTAL" in country or country == "TOTAL":
                holdings["TIC_grand_total"] = value
            elif "FOREIGN OFFICIAL" in country or "OFFICIAL" in country:
                holdings["TIC_foreign_official_total"] = value
            elif any(opec in country for opec in ["SAUDI", "UAE", "KUWAIT",
                                                   "IRAQ", "QATAR", "ALGERIA"]):
                holdings["TIC_opec_holdings"] = (
                    holdings.get("TIC_opec_holdings", 0.0) + value
                )

        # Compute derived indicators
        grand_total = holdings.get("TIC_grand_total", 0.0)
        if grand_total > 0:
            china = holdings.get("TIC_china_holdings", 0.0)
            japan = holdings.get("TIC_japan_holdings", 0.0)
            holdings["TIC_china_share"] = china / grand_total
            holdings["TIC_japan_share"] = japan / grand_total

        if not holdings:
            logger.warning("treasury_tic: no data parsed from response")
            return events

        for indicator, value in holdings.items():
            events.append(
                MacroEvent(
                    source=self.source_name,
                    indicator=indicator,
                    value=value,
                    currency="USD_bn",
                    timestamp=now,
                    freq="1m",
                    metadata={"url": _TIC_URL},
                )
            )

        logger.info("treasury_tic: published %d indicators", len(events))
        return events
