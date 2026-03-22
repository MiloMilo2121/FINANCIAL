"""Financial Ingestion Service entry point.

Starts the APScheduler polling loop for all registered connectors.
Also exposes a minimal FastAPI health endpoint for liveness probes.
"""

import asyncio
import os

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from financial_shared.logging import configure_logging, get_logger
from financial_shared.tracing import configure_tracing
from financial_shared.redis_client import get_sync_redis

from financial_ingestion.config import settings
from financial_ingestion.connectors.alpha_vantage import AlphaVantageConnector
from financial_ingestion.connectors.metalpriceapi import MetalpriceAPIConnector
from financial_ingestion.connectors.metals_api import MetalsAPIConnector
from financial_ingestion.connectors.marketstack import MarketstackConnector
from financial_ingestion.connectors.open_exchange_rates import OpenExchangeRatesConnector
from financial_ingestion.connectors.gpr_index import GPRIndexConnector
from financial_ingestion.connectors.world_gold_council import WorldGoldCouncilConnector
from financial_ingestion.connectors.comex import COMEXConnector
from financial_ingestion.connectors.opensky import OpenSkyConnector
from financial_ingestion.connectors.eosda_satellite import EOSDAConnector
from financial_ingestion.connectors.shipsdna import ShipsDNAConnector
from financial_ingestion.connectors.fred import FREDConnector
from financial_ingestion.connectors.cboe import CBOEConnector
from financial_ingestion.connectors.cftc import CFTCConnector
from financial_ingestion.connectors.eia import EIAConnector
from financial_ingestion.connectors.lbma import LBMAConnector
from financial_ingestion.connectors.treasury_tic import TreasuryTICConnector
from financial_ingestion.connectors.cftc_disagg import CFTCDisaggConnector
from financial_ingestion.connectors.crypto_sentiment import CryptoSentimentConnector
from financial_ingestion.connectors.wgc_demand import WGCDemandConnector
from financial_ingestion.pipeline.publisher import MarketEventPublisher
from financial_ingestion.pipeline.scheduler import ConnectorScheduleConfig, IngestionScheduler
from financial_ingestion.rate_limiting.token_bucket import TokenBucketConfig, TokenBucketLimiter
from financial_ingestion.rate_limiting.sliding_window import SlidingWindowConfig, SlidingWindowLimiter

configure_logging(settings.log_level)
configure_tracing("financial-ingestion")
logger = get_logger(__name__)

app = FastAPI(title="Financial Ingestion Service", version="0.1.0")

# Global scheduler instance
_scheduler: IngestionScheduler | None = None


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "ingestion"})


@app.get("/health/ready")
async def readiness() -> JSONResponse:
    """Readiness probe — checks Redis connectivity."""
    try:
        redis = get_sync_redis(settings.redis_url)
        redis.ping()
        return JSONResponse({"status": "ready"})
    except Exception as exc:
        return JSONResponse({"status": "not_ready", "error": str(exc)}, status_code=503)


@app.on_event("startup")
async def startup() -> None:
    global _scheduler

    # Set Pub/Sub emulator host if configured
    if settings.pubsub_emulator_host:
        os.environ["PUBSUB_EMULATOR_HOST"] = settings.pubsub_emulator_host
    if settings.gcs_emulator_host:
        os.environ["GCS_EMULATOR_HOST"] = settings.gcs_emulator_host

    publisher = MarketEventPublisher(
        project_id=settings.pubsub_project_id,
        topic_name=settings.pubsub_market_events_topic,
    )
    publisher.ensure_topic()

    redis = get_sync_redis(settings.redis_url, pool_size=settings.redis_pool_size)

    # Shared HTTP client for all connectors
    http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    _scheduler = IngestionScheduler(publisher)

    # --- Register connectors ---

    # Alpha Vantage: Token Bucket (allows bursts for historical downloads)
    av_limiter = TokenBucketLimiter(
        redis,
        "alpha_vantage",
        TokenBucketConfig(capacity=5, refill_rate=5 / 60),  # 5 req/min
    )
    _scheduler.register(ConnectorScheduleConfig(
        connector=AlphaVantageConnector(http_client, settings.alpha_vantage_api_key),
        interval_seconds=settings.interval_metals_price,
        rate_limiter=av_limiter,
    ))

    # MetalpriceAPI: Sliding Window (exact quota compliance)
    mp_limiter = SlidingWindowLimiter(
        redis,
        "metalpriceapi",
        SlidingWindowConfig(window_seconds=86400, max_requests=100),  # 100/day
    )
    _scheduler.register(ConnectorScheduleConfig(
        connector=MetalpriceAPIConnector(http_client, settings.metalpriceapi_key),
        interval_seconds=settings.interval_metals_price,
        rate_limiter=mp_limiter,
    ))

    # Metals-API: Sliding Window
    metals_limiter = SlidingWindowLimiter(
        redis,
        "metals_api",
        SlidingWindowConfig(window_seconds=86400, max_requests=100),
    )
    _scheduler.register(ConnectorScheduleConfig(
        connector=MetalsAPIConnector(http_client, settings.metals_api_key),
        interval_seconds=settings.interval_metals_price,
        rate_limiter=metals_limiter,
    ))

    # Marketstack: Sliding Window (monthly quota)
    ms_limiter = SlidingWindowLimiter(
        redis,
        "marketstack",
        SlidingWindowConfig(window_seconds=2592000, max_requests=100),  # 100/month
    )
    _scheduler.register(ConnectorScheduleConfig(
        connector=MarketstackConnector(http_client, settings.marketstack_api_key),
        interval_seconds=86400,  # Daily
        rate_limiter=ms_limiter,
    ))

    # Open Exchange Rates: Token Bucket (hourly updates)
    fx_limiter = TokenBucketLimiter(
        redis,
        "open_exchange_rates",
        TokenBucketConfig(capacity=10, refill_rate=1 / 360),  # ~10/hour
    )
    _scheduler.register(ConnectorScheduleConfig(
        connector=OpenExchangeRatesConnector(http_client, settings.open_exchange_rates_app_id),
        interval_seconds=settings.interval_fx_rates,
        rate_limiter=fx_limiter,
    ))

    # GPR Index: hourly (public data, no strict limits)
    _scheduler.register(ConnectorScheduleConfig(
        connector=GPRIndexConnector(http_client),
        interval_seconds=settings.interval_gpr,
    ))

    # World Gold Council: daily
    _scheduler.register(ConnectorScheduleConfig(
        connector=WorldGoldCouncilConnector(http_client, settings.world_gold_council_api_key),
        interval_seconds=settings.interval_macro,
    ))

    # COMEX: daily
    _scheduler.register(ConnectorScheduleConfig(
        connector=COMEXConnector(http_client, settings.comex_api_key),
        interval_seconds=settings.interval_macro,
    ))

    # OpenSky: hourly
    _scheduler.register(ConnectorScheduleConfig(
        connector=OpenSkyConnector(http_client),
        interval_seconds=settings.interval_alternative,
    ))

    # EOSDA Satellite: hourly
    if settings.eosda_api_key:
        _scheduler.register(ConnectorScheduleConfig(
            connector=EOSDAConnector(http_client, settings.eosda_api_key),
            interval_seconds=settings.interval_alternative,
        ))

    # ShipsDNA: hourly
    if settings.shipsdna_api_key:
        _scheduler.register(ConnectorScheduleConfig(
            connector=ShipsDNAConnector(http_client, settings.shipsdna_api_key),
            interval_seconds=settings.interval_alternative,
        ))

    # ── New free-data connectors ──────────────────────────────────────────────

    # FRED: hourly (rate-limited to 500 req/day on free tier, we fetch 31 series/hour)
    _scheduler.register(ConnectorScheduleConfig(
        connector=FREDConnector(http_client, getattr(settings, "fred_api_key", None)),
        interval_seconds=settings.interval_macro,  # Daily is enough for macro data
    ))

    # CBOE VIX/VVIX: daily (data refreshes once per day after close)
    _scheduler.register(ConnectorScheduleConfig(
        connector=CBOEConnector(http_client),
        interval_seconds=settings.interval_macro,
    ))

    # CFTC COT: daily poll (report released Fridays, but we poll daily)
    _scheduler.register(ConnectorScheduleConfig(
        connector=CFTCConnector(http_client),
        interval_seconds=settings.interval_macro,
    ))

    # EIA energy prices: daily
    if getattr(settings, "eia_api_key", None):
        _scheduler.register(ConnectorScheduleConfig(
            connector=EIAConnector(http_client, settings.eia_api_key),
            interval_seconds=settings.interval_macro,
        ))
    else:
        _scheduler.register(ConnectorScheduleConfig(
            connector=EIAConnector(http_client),
            interval_seconds=settings.interval_macro,
        ))

    # LBMA gold fix: daily (AM/PM fixes published on London trading days)
    _scheduler.register(ConnectorScheduleConfig(
        connector=LBMAConnector(http_client),
        interval_seconds=settings.interval_macro,
    ))

    # ── New free-data connectors (Phase 2 — 334 indicator expansion) ─────────

    # Treasury TIC: monthly (data released ~6 weeks after month-end)
    _scheduler.register(ConnectorScheduleConfig(
        connector=TreasuryTICConnector(http_client),
        interval_seconds=86400,  # Daily poll; data changes monthly
    ))

    # CFTC Disaggregated COT: weekly (report released every Friday)
    _scheduler.register(ConnectorScheduleConfig(
        connector=CFTCDisaggConnector(http_client),
        interval_seconds=86400,  # Daily poll; data changes weekly
    ))

    # Crypto sentiment + gold-backed tokens: daily
    _scheduler.register(ConnectorScheduleConfig(
        connector=CryptoSentimentConnector(http_client),
        interval_seconds=settings.interval_macro,
    ))

    # WGC supply & demand + ETF flows: daily (ETF) / quarterly (demand)
    _scheduler.register(ConnectorScheduleConfig(
        connector=WGCDemandConnector(http_client),
        interval_seconds=86400,  # Daily for ETF; quarterly data auto-cached
    ))

    _scheduler.start()
    logger.info("ingestion.startup_complete")


@app.on_event("shutdown")
async def shutdown() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.stop()
    logger.info("ingestion.shutdown_complete")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")
