"""Geopolitical Risk Index (GPR) connector.

Fetches the GPR index developed by Caldara & Iacoviello (Federal Reserve)
which quantifies geopolitical threats by analyzing global newspaper archives.

Historical data available at: https://www.matteoiacoviello.com/gpr.htm
This connector fetches the publicly available Excel/CSV data files.

The GPR index is a leading indicator for gold's safe-haven function:
- GPR spikes → increased gold demand → bullish signal
- Used in Cross-Modal Attention fusion to modulate ML predictions
"""

import io
from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, MacroEvent

# Publicly available GPR data (CSV format)
GPR_DATA_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.csv"


class GPRIndexConnector(BaseConnector):
    """Fetches Geopolitical Risk Index data."""

    name = "gpr_index"

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch recent GPR daily data."""
        response = await self._get(GPR_DATA_URL)
        content = response.text

        records = []
        lines = content.strip().split("\n")
        if not lines:
            return records

        # Parse CSV header
        headers = [h.strip().strip('"') for h in lines[0].split(",")]

        for line in lines[1:]:
            if not line.strip():
                continue
            values = [v.strip().strip('"') for v in line.split(",")]
            if len(values) < len(headers):
                continue
            record = dict(zip(headers, values))
            records.append(record)

        return records[-30:]  # Return only recent 30 days

    def normalize(self, raw: dict[str, Any]) -> MacroEvent:
        # Date column may be named 'date' or 'DATE'
        date_str = raw.get("date") or raw.get("DATE") or raw.get("Date", "")
        try:
            if "/" in date_str:
                ts = datetime.strptime(date_str, "%m/%d/%Y").replace(tzinfo=timezone.utc)
            else:
                ts = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        # GPR overall index
        gpr_val = raw.get("GPRH") or raw.get("GPR") or raw.get("gpr", 0)

        return MacroEvent(
            timestamp=ts,
            source=self.name,
            asset="GPR",
            asset_class=AssetClass.MACRO,
            price_usd=float(gpr_val) if gpr_val else None,
            currency="INDEX",
            indicator="GPR_INDEX",
            metadata={
                "provider": "gpr_caldara_iacoviello",
                "gpr_h": raw.get("GPRH"),   # Historical GPR
                "gpr_act": raw.get("GPRACT"),  # GPR Acts sub-index
                "gpr_threat": raw.get("GPRTHREAT"),  # GPR Threats sub-index
            },
        )
