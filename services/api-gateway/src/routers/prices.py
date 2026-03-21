"""Prices router — proxies to ingestion/ETL data."""

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from financial_shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{asset}/latest")
async def get_latest_price(
    asset: str,
    ml_service_url: str = "http://localhost:8002",
) -> JSONResponse:
    """Get the latest spot price for a given asset."""
    # In production this reads from the prices BigQuery table or a Redis cache
    # For now returns a mock structure
    return JSONResponse({
        "asset": asset.upper(),
        "price_usd": None,  # Populated from BigQuery in production
        "timestamp": None,
        "sources": ["alpha_vantage", "metalpriceapi", "metals_api"],
    })


@router.get("/{asset}/history")
async def get_price_history(
    asset: str,
    days: int = Query(default=365, ge=1, le=3650),
) -> JSONResponse:
    """Get historical OHLCV data for TradingView chart."""
    return JSONResponse({
        "asset": asset.upper(),
        "days": days,
        "data": [],  # Populated from BigQuery prices table
        "interval": "1d",
    })


@router.get("/{asset}/bars")
async def get_bars_for_tradingview(
    asset: str,
    resolution: str = Query(default="D", description="TradingView resolution: 1, 5, 15, 60, D, W, M"),
    from_ts: int = Query(alias="from"),
    to_ts: int = Query(alias="to"),
) -> JSONResponse:
    """TradingView Datafeed API compatible bars endpoint.

    Called by the frontend CustomDatafeed.ts getBars() method.
    """
    return JSONResponse({
        "s": "ok",
        "t": [],  # Unix timestamps
        "o": [],  # Open
        "h": [],  # High
        "l": [],  # Low
        "c": [],  # Close
        "v": [],  # Volume
    })
