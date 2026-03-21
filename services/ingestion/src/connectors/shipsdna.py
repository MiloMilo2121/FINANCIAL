"""ShipsDNA maritime traffic connector.

Monitors precious metal logistics via maritime AIS data:
- Cargo vessel traffic through major gold shipping lanes
- Port congestion at key gold trading hubs
- Supply chain disruption detection

Used as an alternative data signal for physical gold supply constraints.
API docs: https://www.shipsdna.com/api-documentation
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from financial_ingestion.connectors.base import BaseConnector
from financial_ingestion.schemas.market_event import AssetClass, MarketEvent

SHIPSDNA_API_BASE = "https://api.shipsdna.com/v2"

# Key gold/precious metals shipping ports
_GOLD_PORTS = [
    {"name": "LONDON_THAMES", "locode": "GBLON"},
    {"name": "DUBAI_PORT_RASHID", "locode": "AEDXB"},
    {"name": "HONG_KONG", "locode": "HKHKG"},
    {"name": "MUMBAI", "locode": "INBOM"},
    {"name": "SHANGHAI", "locode": "CNSHA"},
]


class ShipsDNAConnector(BaseConnector):
    """Monitors gold logistics via maritime AIS data from ShipsDNA."""

    name = "shipsdna"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(http_client)
        self._api_key = api_key

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch vessel traffic metrics for gold shipping ports."""
        records = []
        now = datetime.now(timezone.utc)
        headers = {"X-API-Key": self._api_key}

        for port in _GOLD_PORTS:
            try:
                response = await self._get(
                    f"{SHIPSDNA_API_BASE}/ports/{port['locode']}/traffic",
                    params={"vessel_type": "cargo"},
                )
                data = response.json()
                records.append({
                    "port_name": port["name"],
                    "locode": port["locode"],
                    "vessels_in_port": data.get("vessels_in_port", 0),
                    "vessels_expected": data.get("vessels_expected_24h", 0),
                    "congestion_index": data.get("congestion_index"),
                    "timestamp": now.isoformat(),
                })
            except Exception:
                records.append({
                    "port_name": port["name"],
                    "locode": port["locode"],
                    "vessels_in_port": None,
                    "vessels_expected": None,
                    "congestion_index": None,
                    "timestamp": now.isoformat(),
                })

        return records

    def normalize(self, raw: dict[str, Any]) -> MarketEvent:
        ts = datetime.fromisoformat(raw["timestamp"])
        return MarketEvent(
            timestamp=ts,
            source=self.name,
            asset=f"MARITIME/{raw['port_name']}",
            asset_class=AssetClass.ALTERNATIVE,
            price_usd=raw.get("congestion_index"),  # Normalized congestion 0-100
            currency="CONGESTION_INDEX",
            metadata={
                "provider": "shipsdna",
                "port": raw["port_name"],
                "locode": raw["locode"],
                "vessels_in_port": raw.get("vessels_in_port"),
                "vessels_expected_24h": raw.get("vessels_expected"),
                "signal_type": "supply_chain_logistics",
            },
        )
