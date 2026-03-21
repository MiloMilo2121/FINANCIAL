"""Central Pydantic schema for market events flowing through Pub/Sub.

MarketEvent is the contract between the ingestion service and all downstream
consumers (ETL, ML service, sentiment service). Every connector must normalize
its raw output to this schema via its `normalize()` method.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class AssetClass(str, Enum):
    METAL = "metal"
    FX = "fx"
    EQUITY = "equity"
    MACRO = "macro"
    ALTERNATIVE = "alternative"
    NEWS = "news"


class MarketEvent(BaseModel):
    """Canonical market event schema for Pub/Sub messages."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field(description="Connector name, e.g. 'alpha_vantage'")
    asset: str = Field(description="Asset symbol, e.g. 'XAU', 'XAG', 'EURUSD'")
    asset_class: AssetClass
    price_usd: float | None = Field(default=None, ge=0)
    bid: float | None = Field(default=None, ge=0)
    ask: float | None = Field(default=None, ge=0)
    open: float | None = Field(default=None, ge=0)
    high: float | None = Field(default=None, ge=0)
    low: float | None = Field(default=None, ge=0)
    close: float | None = Field(default=None, ge=0)
    volume: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", max_length=3)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime:
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("asset")
    @classmethod
    def uppercase_asset(cls, v: str) -> str:
        return v.upper()

    def to_pubsub_payload(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for Pub/Sub publishing."""
        return self.model_dump(mode="json")


class OHLCVEvent(MarketEvent):
    """OHLCV-specific market event (candlestick data)."""
    asset_class: AssetClass = AssetClass.METAL
    interval: str = Field(description="Time interval, e.g. '1d', '1h', '5m'")


class MacroEvent(MarketEvent):
    """Macroeconomic data point event."""
    asset_class: AssetClass = AssetClass.MACRO
    indicator: str = Field(description="Macro indicator name, e.g. 'CPI', 'FED_RATE'")
    country: str | None = None
    period: str | None = Field(default=None, description="e.g. '2024-Q1', '2024-01'")


class NewsEvent(MarketEvent):
    """News/text event for NLP processing."""
    asset_class: AssetClass = AssetClass.NEWS
    headline: str
    body: str | None = None
    url: str | None = None
    sentiment_raw: float | None = Field(default=None, ge=-1.0, le=1.0)
    language: str = "en"
