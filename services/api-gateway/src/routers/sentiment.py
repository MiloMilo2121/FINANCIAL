"""Sentiment router — proxies to sentiment service."""

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/sentiment", tags=["sentiment"])


class SentimentRequest(BaseModel):
    asset: str = Field(default="XAU")
    context: str = Field(default="")
    time_horizon: str = Field(default="medium")
    current_price: float | None = None


@router.post("/analyze")
async def analyze(
    request: SentimentRequest,
    sentiment_service_url: str = "http://localhost:8003",
) -> JSONResponse:
    """Analyze sentiment for a given asset via Perplexity Sonar."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{sentiment_service_url}/analyze",
                json=request.model_dump(),
            )
            response.raise_for_status()
            return JSONResponse(response.json())
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Sentiment service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)


@router.get("/marks/{asset}")
async def get_geopolitical_marks(
    asset: str,
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> JSONResponse:
    """Get geopolitical event marks for TradingView chart.

    Returns marks in TradingView Marks API format:
    [{id, time, color, text, label, labelFontColor, minSize}]
    """
    # In production: query sentiment_events from BigQuery where
    # geopolitical_risk.threat_level >= HIGH
    return JSONResponse({
        "marks": [],  # Populated from BigQuery sentiment_events table
        "asset": asset.upper(),
    })
