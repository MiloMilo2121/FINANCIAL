"""EIA Connector — U.S. Energy Information Administration.

Fetches crude oil and natural gas spot prices via the EIA open data API v2.
Free API key required: https://www.eia.gov/opendata/register.php

Indicators produced:
  WTI_crude   — West Texas Intermediate crude oil spot price (USD/barrel)
  Brent_crude — Brent crude oil spot price (USD/barrel)
  Natural_gas — Henry Hub natural gas spot price (USD/MMBtu)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from financial_shared.logging import get_logger
from .base import BaseConnector
from ..schemas.market_event import AssetClass, OHLCVEvent

logger = get_logger(__name__)

_EIA_BASE = "https://api.eia.gov/v2"

# EIA v2 API routes and series IDs
_SERIES_MAP = {
    "WTI_crude": {
        "route":     "petroleum/pri/spt/data",
        "series_id": "RWTC",
        "indicator": "WTI_crude",
        "units":     "Dollars per Barrel",
    },
    "Brent_crude": {
        "route":     "petroleum/pri/spt/data",
        "series_id": "RBRTE",
        "indicator": "Brent_crude",
        "units":     "Dollars per Barrel",
    },
    "Natural_gas": {
        "route":     "natural-gas/pri/fut/data",
        "series_id": "RNGWHHD",
        "indicator": "Natural_gas",
        "units":     "Dollars per Million Btu",
    },
}


class EIAConnector(BaseConnector):
    """Fetches energy commodity prices from EIA open data API."""

    name = "eia"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str | None = None) -> None:
        super().__init__(http_client)
        self._api_key = api_key or os.environ.get("EIA_API_KEY", "")

    async def fetch(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not self._api_key:
            logger.warning("eia.no_api_key — set EIA_API_KEY to enable energy data")
            return records

        for key, cfg in _SERIES_MAP.items():
            try:
                url = f"{_EIA_BASE}/{cfg['route']}/"
                params = {
                    "api_key":            self._api_key,
                    "frequency":          "daily",
                    "data[0]":            "value",
                    "facets[series][]":   cfg["series_id"],
                    "sort[0][column]":    "period",
                    "sort[0][direction]": "desc",
                    "length":             1,
                    "offset":             0,
                }
                resp = await self._get(url, params=params)
                data = resp.json()
                obs  = data.get("response", {}).get("data", [])
                if obs:
                    row = obs[0]
                    records.append({
                        "indicator": cfg["indicator"],
                        "series_id": cfg["series_id"],
                        "value":     row.get("value"),
                        "period":    row.get("period"),
                        "units":     cfg["units"],
                    })
            except Exception as exc:
                logger.warning("eia.fetch_failed series=%s error=%s", key, exc)
        return records

    def normalize(self, raw: dict[str, Any]) -> OHLCVEvent:
        period = raw.get("period", "")
        try:
            ts = datetime.fromisoformat(period).replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        value = raw.get("value")
        price = float(value) if value is not None else 0.0

        return OHLCVEvent(
            timestamp  = ts,
            source     = self.name,
            asset      = raw["indicator"].upper(),
            asset_class= AssetClass.ALTERNATIVE,
            price_usd  = price,
            close      = price,
            currency   = "USD",
            interval   = "1d",
            metadata   = {
                "provider":  "eia",
                "series_id": raw["series_id"],
                "units":     raw["units"],
                "indicator": raw["indicator"],
            },
        )
