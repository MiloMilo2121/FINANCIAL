"""Pydantic output schemas for Perplexity Sonar API structured outputs.

These schemas enforce a strict JSON contract on LLM output, eliminating
the need for brittle regex parsers. The LLM is instructed (via prompt
engineering) to return JSON conforming exactly to these Pydantic models.

Key design principles:
  - All fields are typed (no untyped dicts)
  - Floats are bounded (sentiment_score: [-1.0, 1.0])
  - Enums for categorical fields prevent hallucinated values
  - citations field requires source attribution (reduces hallucination)
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class SentimentDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ThreatLevel(int, Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AssetSentiment(BaseModel):
    """Structured sentiment output for a specific asset."""

    asset: str = Field(description="Asset symbol (e.g. 'XAU', 'XAG')")
    sentiment_score: Annotated[float, Field(ge=-1.0, le=1.0)] = Field(
        description="Sentiment score from -1.0 (strongly bearish) to 1.0 (strongly bullish)"
    )
    direction: SentimentDirection
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Model confidence in the sentiment assessment"
    )
    key_drivers: list[str] = Field(
        max_length=5,
        description="Top 3-5 factors driving the sentiment",
    )
    time_horizon: str = Field(
        description="Sentiment time horizon: 'short' (1-7d), 'medium' (1-4w), 'long' (1-3m)"
    )


class GeopoliticalRisk(BaseModel):
    """Geopolitical risk assessment for gold's safe-haven function."""

    threat_level: ThreatLevel
    primary_risk_factors: list[str] = Field(max_length=5)
    affected_regions: list[str]
    gold_impact_direction: SentimentDirection
    gold_impact_magnitude: Annotated[float, Field(ge=0.0, le=1.0)]


class MarketPositioning(BaseModel):
    """Institutional positioning indicators."""

    put_call_ratio: float | None = None
    institutional_flow_direction: SentimentDirection | None = None
    etf_flow_usd_billions: float | None = None
    comex_net_long_change: float | None = None


class SentimentResult(BaseModel):
    """Complete structured sentiment analysis output from Perplexity Sonar.

    This is the canonical contract between the sentiment service and all
    downstream consumers (ML fusion layer, frontend panels).
    """

    asset_sentiment: AssetSentiment
    geopolitical_risk: GeopoliticalRisk
    market_positioning: MarketPositioning
    macro_context: str = Field(
        description="2-3 sentence macro context summary"
    )
    citations: list[str] = Field(
        description="Source URLs or publication references cited",
        min_length=1,
    )
    fact_check_confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Confidence that reported facts are verified against primary sources"
    )
    analysis_timestamp: str = Field(
        description="ISO 8601 timestamp of analysis"
    )

    def to_ml_features(self) -> dict[str, float]:
        """Extract numerical features for ML model input."""
        return {
            "sentiment_score": self.asset_sentiment.sentiment_score,
            "sentiment_confidence": self.asset_sentiment.confidence,
            "geopolitical_threat_level": float(self.geopolitical_risk.threat_level),
            "gold_impact_magnitude": self.geopolitical_risk.gold_impact_magnitude,
            "fact_check_confidence": self.fact_check_confidence,
            "institutional_flow_bullish": (
                1.0 if self.market_positioning.institutional_flow_direction == SentimentDirection.BULLISH
                else -1.0 if self.market_positioning.institutional_flow_direction == SentimentDirection.BEARISH
                else 0.0
            ),
        }
