"""ML Service — FastAPI application entry point.

Endpoints:
  POST /predict      — LSTM-XGBoost hybrid price prediction
  POST /simulate     — Heston Monte Carlo simulation with probability bands
  POST /fuse         — Multimodal fusion (text + price)
  GET  /router/stats — Cache hit rate and cost reduction metrics
  GET  /health       — Liveness probe
  GET  /health/ready — Readiness probe
"""

import os
from datetime import datetime, timezone
from typing import Any

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_shared.logging import configure_logging, get_logger
from financial_shared.tracing import configure_tracing

from financial_ml.config import settings
from financial_ml.models.lstm_model import build_lstm
from financial_ml.models.xgboost_model import XGBoostPriceModel
from financial_ml.models.hybrid_ensemble import HybridEnsemble
from financial_ml.simulation.heston_model import HestonParams, MonteCarloConfig
from financial_ml.simulation.monte_carlo import simulate_heston, compute_var_es
from financial_ml.simulation.probability_bands import extract_bands_for_frontend
from financial_ml.cache.pinecone_client import PineconeSemanticCache
from financial_ml.routing.model_router import PredictionRouter, ModelTier
from financial_ml.features import FeaturePipeline, INDICATOR_REGISTRY

configure_logging(settings.log_level)
configure_tracing("financial-ml")
logger = get_logger(__name__)

app = FastAPI(title="Financial ML Service", version="0.1.0")

# Global model instances (loaded at startup)
_lstm: Any = None
_xgb: Any = None
_ensemble: HybridEnsemble | None = None
_cache: PineconeSemanticCache | None = None
_router: PredictionRouter | None = None
_feature_pipeline: FeaturePipeline | None = None


# ---- Request / Response schemas ----

class PredictRequest(BaseModel):
    asset: str = Field(default="XAU", description="Asset symbol")
    price_history: list[float] = Field(
        description="Historical closing prices (at least 60 data points)"
    )
    macro_features: dict[str, float] = Field(
        default_factory=dict,
        description="Macro indicators: dxy, real_yield, gpr_index, etc.",
    )
    forecast_days: int = Field(default=5, ge=1, le=30)
    news_summary: str | None = Field(default=None, description="Recent news summary for fusion")


class PredictResponse(BaseModel):
    asset: str
    predictions: list[float]         # Mean price forecasts
    uncertainty_std: list[float]      # Prediction std dev
    model_tier: str                   # Which model tier was used
    cache_hit: bool
    forecast_days: int


class SimulateRequest(BaseModel):
    asset: str = Field(default="XAU")
    current_price: float = Field(gt=0)
    historical_prices: list[float] = Field(
        description="Historical prices for Heston calibration (min 60)"
    )
    n_paths: int = Field(default=10000, ge=100, le=100000)
    horizon_days: int = Field(default=30, ge=1, le=365)
    random_seed: int | None = None


class SimulateResponse(BaseModel):
    asset: str
    current_price: float
    probability_bands: list[dict]    # [{timestamp, date, p5, p25, p50, p75, p95}]
    var_95: dict                     # Value at Risk metrics
    heston_params: dict
    computation_time_ms: float
    n_paths: int


# ---- Endpoints ----

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "ml-service"})


@app.get("/health/ready")
async def readiness() -> JSONResponse:
    if _lstm is None:
        return JSONResponse({"status": "not_ready", "reason": "models_not_loaded"}, status_code=503)
    return JSONResponse({"status": "ready"})


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    """Run LSTM-XGBoost hybrid price prediction."""
    if len(request.price_history) < settings.lstm_sequence_length:
        raise HTTPException(
            status_code=422,
            detail=f"price_history must have at least {settings.lstm_sequence_length} data points",
        )

    # Build input tensor from recent history
    prices = np.array(request.price_history[-settings.lstm_sequence_length:], dtype=np.float32)
    # Normalize by last price for scale invariance
    prices_norm = prices / prices[-1]

    # Build feature vector: price + simple technical indicators
    returns = np.diff(prices_norm, prepend=prices_norm[0])
    features = np.stack([prices_norm, returns], axis=1)  # (seq_len, 2)

    # Add macro features as a constant channel
    macro_vals = list(request.macro_features.values()) or [0.0]
    macro_arr = np.full((settings.lstm_sequence_length, len(macro_vals)), macro_vals)
    features = np.concatenate([features, macro_arr], axis=1)  # (seq_len, 2+n_macro)

    x_seq = torch.FloatTensor(features).unsqueeze(0)  # (1, seq_len, features)

    cache_hit = False
    tier = ModelTier.LIGHTWEIGHT

    if _ensemble is not None:
        # Build 175-indicator tabular feature vector via FeaturePipeline
        if _feature_pipeline is not None:
            # Reconstruct OHLCV: use close as proxy (open=high=low=close, volume=0)
            close_arr = np.array(request.price_history[-settings.lstm_sequence_length:],
                                 dtype=np.float32)
            ohlcv_proxy = np.column_stack([close_arr, close_arr, close_arr, close_arr,
                                           np.ones_like(close_arr)])
            tabular = _feature_pipeline.transform(
                ohlcv_proxy, external=request.macro_features
            ).reshape(1, -1)
        else:
            tabular = np.array([list(request.macro_features.values()) or [0.0]], dtype=np.float32)
        result = _ensemble.predict(features[np.newaxis], tabular)
        predictions = (result["prediction"] * prices[-1]).tolist()
        uncertainty = (result["uncertainty_std"] * prices[-1]).tolist()
        tier = ModelTier.HYBRID_ENSEMBLE
    else:
        # Fallback: linear extrapolation (for dev without trained model)
        last = request.price_history[-1]
        trend = (last - request.price_history[-5]) / 5 if len(request.price_history) >= 5 else 0
        predictions = [last + trend * (i + 1) for i in range(request.forecast_days)]
        uncertainty = [last * 0.01] * request.forecast_days
        tier = ModelTier.LIGHTWEIGHT

    return PredictResponse(
        asset=request.asset,
        predictions=predictions[:request.forecast_days],
        uncertainty_std=uncertainty[:request.forecast_days],
        model_tier=tier.value,
        cache_hit=cache_hit,
        forecast_days=request.forecast_days,
    )


@app.post("/simulate", response_model=SimulateResponse)
async def simulate(request: SimulateRequest) -> SimulateResponse:
    """Run Heston Monte Carlo simulation."""
    prices = np.array(request.historical_prices, dtype=np.float64)

    # Calibrate Heston params from historical data
    heston_params = HestonParams.calibrate_from_history(prices)
    heston_params.S0 = request.current_price

    mc_config = MonteCarloConfig(
        n_paths=request.n_paths,
        horizon_days=request.horizon_days,
        random_seed=request.random_seed,
    )

    result = simulate_heston(heston_params, mc_config)
    var_metrics = compute_var_es(result.paths[:, -1], request.current_price)

    bands = extract_bands_for_frontend(result, datetime.now(timezone.utc))

    return SimulateResponse(
        asset=request.asset,
        current_price=request.current_price,
        probability_bands=bands,
        var_95=var_metrics,
        heston_params={
            "S0": heston_params.S0,
            "v0": round(heston_params.v0, 6),
            "mu": heston_params.mu,
            "kappa": round(heston_params.kappa, 4),
            "theta": round(heston_params.theta, 6),
            "sigma_v": heston_params.sigma_v,
            "rho": round(heston_params.rho, 4),
            "feller_satisfied": heston_params.validate_feller_condition(),
        },
        computation_time_ms=round(result.computation_time_ms, 2),
        n_paths=request.n_paths,
    )


@app.get("/router/stats")
async def router_stats() -> JSONResponse:
    if _router is None:
        return JSONResponse({"status": "router_not_initialized"})
    return JSONResponse(_router.get_stats())


@app.get("/features/registry")
async def features_registry() -> JSONResponse:
    """Return the full indicator registry metadata (175 indicators)."""
    registry_data = {
        name: {
            "category":    meta.category,
            "description": meta.description,
            "source":      meta.source,
            "is_computed": meta.is_computed,
            "freq":        meta.freq,
            "tags":        meta.tags,
        }
        for name, meta in INDICATOR_REGISTRY.items()
    }
    return JSONResponse({
        "total": len(registry_data),
        "indicators": registry_data,
    })


@app.on_event("startup")
async def startup() -> None:
    global _lstm, _xgb, _ensemble, _cache, _router, _feature_pipeline

    if settings.gcs_emulator_host:
        os.environ["GCS_EMULATOR_HOST"] = settings.gcs_emulator_host

    # Initialize Pinecone cache
    _cache = PineconeSemanticCache(
        api_key=settings.pinecone_api_key,
        index_name=settings.pinecone_index_name,
        similarity_threshold=settings.pinecone_semantic_cache_threshold,
    )

    # Initialize router (models are loaded lazily or from GCS in prod)
    _router = PredictionRouter(
        cache=_cache,
        gpr_threshold=settings.gpr_threshold_for_multimodal,
    )

    # Initialize 175-indicator FeaturePipeline
    _feature_pipeline = FeaturePipeline(INDICATOR_REGISTRY)
    logger.info("ml.feature_pipeline_initialized indicators=%d", len(INDICATOR_REGISTRY))

    # Try to load pre-trained models if they exist
    try:
        # In production, models are loaded from GCS bucket
        # For dev, they may not exist yet — fallback to linear extrapolation
        n_features = 2  # price + returns; expands with macro features
        _lstm = build_lstm(
            n_features=n_features + 3,  # + 3 macro feature slots
            hidden_size=settings.lstm_hidden_size,
            num_layers=settings.lstm_num_layers,
            dropout=settings.lstm_dropout,
            forecast_horizon=settings.lstm_forecast_horizon,
        )
        _xgb = XGBoostPriceModel(
            n_estimators=settings.xgboost_n_estimators,
            max_depth=settings.xgboost_max_depth,
        )
        logger.info("ml.models_initialized")
    except Exception as exc:
        logger.warning("ml.model_init_failed", error=str(exc))

    logger.info("ml.startup_complete")


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
