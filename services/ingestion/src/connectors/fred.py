"""FRED Connector — Federal Reserve Economic Data.

Fetches 31 macro series from the St. Louis Fed FRED API.
Free tier: no key required for CSV downloads; API key unlocks higher
request quotas (register free at https://fred.stlouisfed.org/docs/api/api_key.html).

Series fetched and their indicator mappings:
  DFF      → Fed_Funds_Rate
  GS2      → Treasury_2Y
  GS5      → Treasury_5Y
  GS10     → Treasury_10Y
  GS30     → Treasury_30Y
  DFII10   → TIPS_10Y
  T10Y2Y   → Yield_curve_10_2
  T10Y3M   → Yield_curve_10_3m
  T5YIE    → Breakeven_5Y
  T10YIE   → Breakeven_10Y
  CPIAUCSL → CPI_YoY  (YoY% computed)
  CPILFESL → CPI_Core_YoY
  PPIACO   → PPI_YoY
  PCEPI    → PCE_YoY
  PCEPILFE → PCE_Core_YoY
  M2SL     → M2_YoY
  BOGMBASE → Monetary_base_growth
  DTWEXBGS → Trade_weighted_dollar
  DEXUSEU  → EUR_USD
  DEXJPUS  → USD_JPY
  DEXCHUS  → USD_CNY
  DEXUSUK  → GBP_USD
  DEXSZUS  → CHF_USD
  UNRATE   → Unemployment_rate
  PAYEMS   → NFP_change
  ICSA     → Initial_jobless_claims
  RSAFS    → Retail_sales_YoY
  INDPRO   → Industrial_production_YoY
  TEDRATE  → TED_spread
  BAMLC0A0CM  → IG_credit_spread
  BAMLH0A0HYM2 → HY_credit_spread
"""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from financial_shared.logging import get_logger
from .base import BaseConnector
from ..schemas.market_event import AssetClass, MacroEvent

logger = get_logger(__name__)

# Maps FRED series ID → (indicator_name, currency, transform)
# transform: "level" | "yoy_pct" | "mom_diff"
_SERIES_MAP: dict[str, tuple[str, str, str]] = {
    "DFF":          ("Fed_Funds_Rate",         "PERCENT", "level"),
    "GS2":          ("Treasury_2Y",            "PERCENT", "level"),
    "GS5":          ("Treasury_5Y",            "PERCENT", "level"),
    "GS10":         ("Treasury_10Y",           "PERCENT", "level"),
    "GS30":         ("Treasury_30Y",           "PERCENT", "level"),
    "DFII10":       ("TIPS_10Y",               "PERCENT", "level"),
    "T10Y2Y":       ("Yield_curve_10_2",       "PERCENT", "level"),
    "T10Y3M":       ("Yield_curve_10_3m",      "PERCENT", "level"),
    "T5YIE":        ("Breakeven_5Y",           "PERCENT", "level"),
    "T10YIE":       ("Breakeven_10Y",          "PERCENT", "level"),
    "CPIAUCSL":     ("CPI_YoY",               "PERCENT", "yoy_pct"),
    "CPILFESL":     ("CPI_Core_YoY",          "PERCENT", "yoy_pct"),
    "PPIACO":       ("PPI_YoY",               "PERCENT", "yoy_pct"),
    "PCEPI":        ("PCE_YoY",               "PERCENT", "yoy_pct"),
    "PCEPILFE":     ("PCE_Core_YoY",          "PERCENT", "yoy_pct"),
    "M2SL":         ("M2_YoY",               "PERCENT", "yoy_pct"),
    "BOGMBASE":     ("Monetary_base_growth",  "PERCENT", "yoy_pct"),
    "DTWEXBGS":     ("Trade_weighted_dollar", "INDEX",   "level"),
    "DEXUSEU":      ("EUR_USD",              "USD",     "level"),
    "DEXJPUS":      ("USD_JPY",             "USD",     "level"),
    "DEXCHUS":      ("USD_CNY",             "USD",     "level"),
    "DEXUSUK":      ("GBP_USD",             "USD",     "level"),
    "DEXSZUS":      ("CHF_USD",             "USD",     "level"),
    "UNRATE":       ("Unemployment_rate",   "PERCENT", "level"),
    "PAYEMS":       ("NFP_change",          "K",       "mom_diff"),
    "ICSA":         ("Initial_jobless_claims","K",      "level"),
    "RSAFS":        ("Retail_sales_YoY",    "PERCENT", "yoy_pct"),
    "INDPRO":       ("Industrial_production_YoY","PERCENT","yoy_pct"),
    "TEDRATE":      ("TED_spread",          "PERCENT", "level"),
    "BAMLC0A0CM":   ("IG_credit_spread",    "PERCENT", "level"),
    "BAMLH0A0HYM2": ("HY_credit_spread",    "PERCENT", "level"),
}

_FRED_CSV_BASE  = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_FRED_API_BASE  = "https://api.stlouisfed.org/fred/series/observations"


class FREDConnector(BaseConnector):
    """Fetches 31 macro time series from the FRED API."""

    name = "fred"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str | None = None) -> None:
        super().__init__(http_client)
        self._api_key = api_key or os.environ.get("FRED_API_KEY", "")

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch the latest value for each FRED series."""
        records: list[dict[str, Any]] = []
        for series_id, (indicator, currency, transform) in _SERIES_MAP.items():
            try:
                rows = await self._fetch_series(series_id, limit=14)
                if not rows:
                    continue
                # Filter out "." (missing values) and take the last valid value
                valid = [(d, v) for d, v in rows if v != "."]
                if not valid:
                    continue
                if transform == "yoy_pct":
                    # Need 13 observations for YoY: (latest / same_month_last_year - 1) * 100
                    valid_12m = [(d, v) for d, v in rows if v != "."]
                    if len(valid_12m) >= 13:
                        val_now  = float(valid_12m[-1][1])
                        val_year = float(valid_12m[-13][1])
                        value    = (val_now / (val_year + 1e-12) - 1.0) * 100.0
                    else:
                        value = float(valid[-1][1])
                elif transform == "mom_diff":
                    if len(valid) >= 2:
                        value = float(valid[-1][1]) - float(valid[-2][1])
                    else:
                        value = float(valid[-1][1])
                else:
                    value = float(valid[-1][1])

                date_str = valid[-1][0]
                records.append({
                    "series_id": series_id,
                    "indicator": indicator,
                    "currency":  currency,
                    "value":     value,
                    "date":      date_str,
                    "transform": transform,
                })
            except Exception as exc:
                logger.warning("fred.fetch_failed series=%s error=%s", series_id, exc)
        return records

    async def _fetch_series(self, series_id: str, limit: int = 14) -> list[tuple[str, str]]:
        """Fetch recent observations. Returns list of (date_str, value_str)."""
        if self._api_key:
            return await self._fetch_via_api(series_id, limit)
        return await self._fetch_via_csv(series_id, limit)

    async def _fetch_via_csv(self, series_id: str, limit: int) -> list[tuple[str, str]]:
        """Use the public CSV endpoint (no key required)."""
        resp = await self._get(_FRED_CSV_BASE, params={"id": series_id})
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)[1:]  # skip header
        return [(row[0], row[1]) for row in rows if len(row) >= 2][-limit:]

    async def _fetch_via_api(self, series_id: str, limit: int) -> list[tuple[str, str]]:
        """Use the JSON API (requires free key)."""
        params = {
            "series_id":  series_id,
            "api_key":    self._api_key,
            "file_type":  "json",
            "limit":      limit,
            "sort_order": "desc",
        }
        resp = await self._get(_FRED_API_BASE, params=params)
        data = resp.json()
        obs  = data.get("observations", [])
        rows = [(o["date"], o["value"]) for o in obs if "date" in o and "value" in o]
        return list(reversed(rows))

    def normalize(self, raw: dict[str, Any]) -> MacroEvent:
        date_str = raw["date"]
        ts = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        return MacroEvent(
            timestamp  = ts,
            source     = self.name,
            asset      = f"MACRO/US/{raw['indicator']}",
            asset_class= AssetClass.MACRO,
            price_usd  = float(raw["value"]),
            currency   = raw["currency"],
            indicator  = raw["indicator"],
            country    = "US",
            period     = raw["date"],
            metadata   = {"series_id": raw["series_id"], "transform": raw["transform"]},
        )
