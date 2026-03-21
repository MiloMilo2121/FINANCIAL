"""OpenSky Network connector.

Monitors cargo flight activity using ADS-B transponder data.
Tracks aircraft movements between major gold trading hubs
(London, Zurich, Dubai, Hong Kong, New York) as a proxy for
physical gold logistics and supply chain disruptions.

OpenSky REST API: https://opensky-network.org/apidoc/rest.html
Public API — no key required, but rate limited to 100 req/day.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, MarketEvent

OPENSKY_API = "https://opensky-network.org/api"

# Bounding boxes for major gold hub airports [lon_min, lat_min, lon_max, lat_max]
_GOLD_HUB_AIRPORTS = {
    "LHR": {"lamin": 51.4, "lomin": -0.5, "lamax": 51.6, "lomax": -0.1},    # London Heathrow
    "ZRH": {"lamin": 47.4, "lomin": 8.5, "lamax": 47.5, "lomax": 8.6},       # Zurich
    "DXB": {"lamin": 25.2, "lomin": 55.3, "lamax": 25.3, "lomax": 55.4},     # Dubai
    "HKG": {"lamin": 22.3, "lomin": 113.9, "lamax": 22.4, "lomax": 114.0},   # Hong Kong
}


class OpenSkyConnector(BaseConnector):
    """Monitors cargo flight activity at gold trading hubs via ADS-B."""

    name = "opensky"

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch current aircraft count over gold hub airports."""
        records = []
        now = datetime.now(timezone.utc)

        for airport, bbox in _GOLD_HUB_AIRPORTS.items():
            try:
                response = await self._get(
                    f"{OPENSKY_API}/states/all",
                    params=bbox,
                )
                data = response.json()
                states = data.get("states", []) or []
                records.append({
                    "airport": airport,
                    "aircraft_count": len(states),
                    "timestamp": now.isoformat(),
                })
            except Exception:
                records.append({
                    "airport": airport,
                    "aircraft_count": None,
                    "timestamp": now.isoformat(),
                })

        return records

    def normalize(self, raw: dict[str, Any]) -> MarketEvent:
        ts = datetime.fromisoformat(raw["timestamp"])
        return MarketEvent(
            timestamp=ts,
            source=self.name,
            asset=f"LOGISTICS/CARGO/{raw['airport']}",
            asset_class=AssetClass.ALTERNATIVE,
            price_usd=float(raw["aircraft_count"]) if raw.get("aircraft_count") is not None else None,
            currency="COUNT",
            metadata={
                "provider": "opensky_network",
                "airport": raw["airport"],
                "aircraft_count": raw.get("aircraft_count"),
                "signal_type": "cargo_traffic_proxy",
            },
        )
