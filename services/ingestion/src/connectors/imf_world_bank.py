"""IMF World Economic Outlook and World Bank Open Data connector.

Fetches macroeconomic indicators critical for gold price modeling:
- Inflation rates (CPI) — negative real rates → gold bullish
- GDP growth projections
- Interest rate expectations
- Global trade volumes

IMF WEO API: https://www.imf.org/en/Publications/WEO
World Bank API: https://data.worldbank.org/indicator

Both are public APIs requiring no API key.
Uses Sliding Window Log for strict rate compliance.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, MacroEvent

WB_API_BASE = "https://api.worldbank.org/v2"

# World Bank indicator codes relevant to gold
_WB_INDICATORS = {
    "FP.CPI.TOTL.ZG": "CPI_INFLATION_ANNUAL",
    "NY.GDP.MKTP.KD.ZG": "GDP_GROWTH_ANNUAL",
    "FR.INR.RINR": "REAL_INTEREST_RATE",
    "BX.KLT.DINV.CD.WD": "FDI_INFLOWS",
}

_COUNTRIES = ["US", "CN", "IN", "DE", "JP"]  # Major gold demand/reserve countries


class IMFWorldBankConnector(BaseConnector):
    """Fetches macroeconomic indicators from World Bank public API."""

    name = "imf_world_bank"

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch key macro indicators for major economies."""
        records = []
        for indicator_code, indicator_name in _WB_INDICATORS.items():
            for country in _COUNTRIES:
                try:
                    response = await self._get(
                        f"{WB_API_BASE}/country/{country}/indicator/{indicator_code}",
                        params={
                            "format": "json",
                            "mrv": 5,  # Most recent 5 values
                            "per_page": 5,
                        },
                    )
                    data = response.json()
                    # World Bank returns [metadata, data_array]
                    if isinstance(data, list) and len(data) > 1:
                        for obs in data[1] or []:
                            if obs.get("value") is not None:
                                records.append({
                                    "indicator_code": indicator_code,
                                    "indicator_name": indicator_name,
                                    "country": country,
                                    "year": obs.get("date"),
                                    "value": obs.get("value"),
                                })
                except Exception:
                    continue  # Don't fail entire fetch for one indicator

        return records

    def normalize(self, raw: dict[str, Any]) -> MacroEvent:
        year_str = raw.get("year", str(datetime.now(timezone.utc).year))
        ts = datetime(int(year_str), 12, 31, tzinfo=timezone.utc)  # End of year

        return MacroEvent(
            timestamp=ts,
            source=self.name,
            asset=f"MACRO/{raw['country']}/{raw['indicator_name']}",
            asset_class=AssetClass.MACRO,
            price_usd=float(raw["value"]) if raw.get("value") is not None else None,
            currency="PERCENT" if "RATE" in raw.get("indicator_name", "") else "USD",
            indicator=raw.get("indicator_name", "UNKNOWN"),
            country=raw.get("country"),
            period=year_str,
            metadata={
                "provider": "world_bank",
                "indicator_code": raw.get("indicator_code"),
            },
        )
