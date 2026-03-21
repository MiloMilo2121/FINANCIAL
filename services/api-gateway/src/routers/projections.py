"""Projections router — proxies to ML service."""

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/projections", tags=["projections"])


class PredictRequest(BaseModel):
    asset: str = Field(default="XAU")
    price_history: list[float]
    macro_features: dict[str, float] = Field(default_factory=dict)
    forecast_days: int = Field(default=5, ge=1, le=30)
    news_summary: str | None = None


class SimulateRequest(BaseModel):
    asset: str = Field(default="XAU")
    current_price: float
    historical_prices: list[float]
    n_paths: int = Field(default=10000, ge=100, le=100000)
    horizon_days: int = Field(default=30, ge=1, le=365)


@router.post("/predict")
async def predict(request: PredictRequest, ml_service_url: str = "http://localhost:8002") -> JSONResponse:
    """Get LSTM-XGBoost price predictions from ML service."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ml_service_url}/predict",
                json=request.model_dump(),
            )
            response.raise_for_status()
            return JSONResponse(response.json())
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="ML service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)


@router.post("/simulate")
async def simulate(request: SimulateRequest, ml_service_url: str = "http://localhost:8002") -> JSONResponse:
    """Run Monte Carlo simulation and return probability bands."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ml_service_url}/simulate",
                json=request.model_dump(),
            )
            response.raise_for_status()
            return JSONResponse(response.json())
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="ML service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
