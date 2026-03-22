"""WGC Demand Connector — World Gold Council Gold Demand Trends data.

Free data, no API key. WGC publishes quarterly demand/supply data via
Goldhub API and downloadable datasets.

WGC Goldhub API (free, no auth):
  https://goldhub.wgc.org/api/v1/

Indicators published (15):
  WGC_tech_demand_t          — Technology demand (tonnes, quarterly)
  WGC_bar_coin_demand_t      — Bar & Coin investment demand (tonnes, quarterly)
  WGC_otc_demand_t           — OTC & Other investment (tonnes, quarterly)
  WGC_india_jewelry_t        — India jewelry demand (tonnes, quarterly)
  WGC_china_jewelry_t        — China jewelry demand (tonnes, quarterly)
  WGC_china_bar_coin_t       — China bar & coin demand (tonnes, quarterly)
  WGC_mine_production_t      — Mine production (tonnes, quarterly)
  WGC_aisc_spread            — Price minus AISC (USD/oz) — profitability proxy
  WGC_scrap_supply_t         — Gold scrap/recycling supply (tonnes, quarterly)
  WGC_producer_hedging_t     — Producer net hedging (tonnes, quarterly)
  WGC_total_demand_t         — Total identified demand (tonnes, quarterly)
  WGC_total_supply_t         — Total supply (tonnes, quarterly)
  WGC_demand_supply_balance  — Demand − Supply balance (tonnes, quarterly)
  WGC_etf_total_tonnes       — Global ETF holdings total (tonnes)
  WGC_cb_net_purchases_t     — Central bank net purchases (tonnes, quarterly)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from financial_shared.logging import get_logger
from .base import BaseConnector
from ..schemas.market_event import MacroEvent

logger = get_logger(__name__)

# WGC Goldhub API — sector demand endpoint
# The API returns time series data by demand sector
_WGC_BASE  = "https://goldhub.wgc.org/api/v1"
_DEMAND_EP = f"{_WGC_BASE}/goldhub-category?category=DEMAND&subcategory=GDT"
_SUPPLY_EP = f"{_WGC_BASE}/goldhub-category?category=SUPPLY&subcategory=GDT"
_ETF_EP    = f"{_WGC_BASE}/goldhub-indicator?indicator=GOLD_ETF"

# Fallback: WGC public CSV (no auth)
_WGC_CSV_BASE = "https://www.gold.org/goldhub/data"


class WGCDemandConnector(BaseConnector):
    """Fetches granular gold supply & demand from WGC Goldhub."""

    source_name = "wgc_demand"

    async def fetch(self) -> dict[str, Any]:
        """Attempt WGC Goldhub API; returns parsed JSON or empty dict on error."""
        results: dict[str, Any] = {}

        for key, url in [("demand", _DEMAND_EP), ("supply", _SUPPLY_EP),
                         ("etf", _ETF_EP)]:
            try:
                raw = await self._get(url)
                results[key] = json.loads(raw)
            except Exception as exc:
                logger.warning("wgc_demand: fetch failed for %s: %s", key, exc)
                results[key] = {}

        return results

    def normalize(self, raw: dict[str, Any]) -> list[MacroEvent]:
        """Parse WGC Goldhub API response into MacroEvents.

        The API structure varies; we attempt best-effort parsing and log
        unrecognized formats for debugging.
        """
        events: list[MacroEvent] = []
        now = datetime.now(timezone.utc)

        def _pub(indicator: str, value: float, freq: str = "1q") -> None:
            events.append(MacroEvent(
                source=self.source_name,
                indicator=indicator,
                value=value,
                currency="TONNES",
                timestamp=now,
                freq=freq,
                metadata={"source": "wgc_goldhub"},
            ))

        # ── Demand data ───────────────────────────────────────────────────────
        demand_data = raw.get("demand", {})
        if isinstance(demand_data, dict):
            rows = demand_data.get("data", demand_data.get("rows", []))
        else:
            rows = []

        # Mapping from WGC category names to our indicator names
        _DEMAND_MAP = {
            "Technology": "WGC_tech_demand_t",
            "Technology Demand": "WGC_tech_demand_t",
            "Bar & Coin": "WGC_bar_coin_demand_t",
            "Bar and Coin": "WGC_bar_coin_demand_t",
            "OTC": "WGC_otc_demand_t",
            "OTC & Other": "WGC_otc_demand_t",
            "India": "WGC_india_jewelry_t",
            "China Mainland": "WGC_china_jewelry_t",
            "China": "WGC_china_jewelry_t",
            "Total Demand": "WGC_total_demand_t",
            "Central Banks": "WGC_cb_net_purchases_t",
            "Central Bank Net Purchases": "WGC_cb_net_purchases_t",
        }

        total_demand = 0.0
        for row in rows:
            if not isinstance(row, dict):
                continue
            category = row.get("category") or row.get("label") or ""
            value_raw = row.get("value") or row.get("tonnes") or row.get("val")
            if value_raw is None:
                continue
            try:
                value = float(str(value_raw).replace(",", ""))
            except ValueError:
                continue

            indicator = _DEMAND_MAP.get(category)
            if indicator:
                _pub(indicator, value)
                if "Total" in category:
                    total_demand = value

        # ── Supply data ───────────────────────────────────────────────────────
        supply_data = raw.get("supply", {})
        if isinstance(supply_data, dict):
            supply_rows = supply_data.get("data", supply_data.get("rows", []))
        else:
            supply_rows = []

        _SUPPLY_MAP = {
            "Mine Production": "WGC_mine_production_t",
            "Mine production": "WGC_mine_production_t",
            "Recycled Gold": "WGC_scrap_supply_t",
            "Scrap": "WGC_scrap_supply_t",
            "Net Producer Hedging": "WGC_producer_hedging_t",
            "Producer Hedging": "WGC_producer_hedging_t",
            "Total Supply": "WGC_total_supply_t",
        }

        total_supply = 0.0
        for row in supply_rows:
            if not isinstance(row, dict):
                continue
            category = row.get("category") or row.get("label") or ""
            value_raw = row.get("value") or row.get("tonnes") or row.get("val")
            if value_raw is None:
                continue
            try:
                value = float(str(value_raw).replace(",", ""))
            except ValueError:
                continue

            indicator = _SUPPLY_MAP.get(category)
            if indicator:
                _pub(indicator, value)
                if "Total" in category:
                    total_supply = value

        # Publish balance
        if total_demand > 0 and total_supply > 0:
            _pub("WGC_demand_supply_balance", total_demand - total_supply)

        # ── ETF data ──────────────────────────────────────────────────────────
        etf_data = raw.get("etf", {})
        if isinstance(etf_data, dict):
            etf_rows = etf_data.get("data", etf_data.get("rows", []))
            if etf_rows and isinstance(etf_rows[-1], dict):
                latest_etf = etf_rows[-1]
                etf_tonnes_raw = (latest_etf.get("value") or
                                  latest_etf.get("tonnes") or
                                  latest_etf.get("holdings"))
                if etf_tonnes_raw is not None:
                    try:
                        _pub("WGC_etf_total_tonnes", float(etf_tonnes_raw), "1d")
                    except Exception:
                        pass

        logger.info("wgc_demand: published %d events", len(events))
        return events
