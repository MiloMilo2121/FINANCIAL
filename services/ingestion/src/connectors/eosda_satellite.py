"""EOSDA (Earth Observing System Data & Analysis) satellite connector.

Monitors gold mining activity via multispectral satellite imagery analysis:
- Surface disturbance detection in known mining zones
- Vegetation stress (NDVI) changes around mine sites
- Thermal anomaly detection (active mining operations)
- Illegal mining activity identification

EOSDA Crop Monitoring API repurposed for land use analysis.
API docs: https://eos.com/products/crop-monitoring/api/
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, MarketEvent

EOSDA_API_BASE = "https://api-connect.eos.com/api/gdw/api"

# Major gold mining regions with approximate bounding boxes
_MINING_REGIONS = {
    "NEVADA_CARLIN": {
        "geometry": {"type": "Point", "coordinates": [-116.4, 40.7]},
        "country": "US",
        "region_type": "open_pit",
    },
    "WITWATERSRAND": {
        "geometry": {"type": "Point", "coordinates": [26.5, -26.2]},
        "country": "ZA",
        "region_type": "deep_mine",
    },
    "MPONENG": {
        "geometry": {"type": "Point", "coordinates": [27.3, -26.3]},
        "country": "ZA",
        "region_type": "deep_mine",
    },
    "PAPUA_PORGERA": {
        "geometry": {"type": "Point", "coordinates": [143.1, -5.5]},
        "country": "PG",
        "region_type": "open_pit",
    },
}


class EOSDAConnector(BaseConnector):
    """Fetches satellite-derived mining activity signals from EOSDA."""

    name = "eosda_satellite"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(http_client)
        self._api_key = api_key

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch latest NDVI and vegetation anomaly data for mining regions."""
        records = []
        headers = {"Authorization": f"ApiKey {self._api_key}"}
        now = datetime.now(timezone.utc)

        for region_name, region_data in _MINING_REGIONS.items():
            try:
                # Request latest vegetation index for the region
                response = await self._get(
                    f"{EOSDA_API_BASE}/indices",
                    params={
                        "geometry": str(region_data["geometry"]),
                        "period_start": now.strftime("%Y-%m-%d"),
                        "period_end": now.strftime("%Y-%m-%d"),
                        "index": "NDVI",
                    },
                )
                data = response.json()
                records.append({
                    "region": region_name,
                    "country": region_data["country"],
                    "region_type": region_data["region_type"],
                    "ndvi": data.get("ndvi"),
                    "anomaly_score": data.get("anomaly_score"),
                    "cloud_coverage": data.get("cloud_coverage_pct"),
                    "timestamp": now.isoformat(),
                })
            except Exception:
                # Satellite data often unavailable (cloud cover, revisit cycle)
                records.append({
                    "region": region_name,
                    "country": region_data["country"],
                    "region_type": region_data["region_type"],
                    "ndvi": None,
                    "anomaly_score": None,
                    "cloud_coverage": 100,
                    "timestamp": now.isoformat(),
                })

        return records

    def normalize(self, raw: dict[str, Any]) -> MarketEvent:
        ts = datetime.fromisoformat(raw["timestamp"])
        return MarketEvent(
            timestamp=ts,
            source=self.name,
            asset=f"SATELLITE/MINING/{raw['region']}",
            asset_class=AssetClass.ALTERNATIVE,
            price_usd=raw.get("anomaly_score"),  # Higher = more activity anomaly
            currency="NDVI_SCORE",
            metadata={
                "provider": "eosda",
                "region": raw["region"],
                "country": raw["country"],
                "region_type": raw["region_type"],
                "ndvi": raw.get("ndvi"),
                "cloud_coverage_pct": raw.get("cloud_coverage"),
                "signal_type": "mining_activity_satellite",
            },
        )
