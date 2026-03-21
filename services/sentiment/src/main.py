"""Sentiment Service entry point.

Exposes:
  POST /analyze          — On-demand sentiment analysis via Perplexity
  GET  /health           — Liveness probe
  GET  /health/ready     — Readiness probe
  GET  /consumer/stats   — Pub/Sub consumer statistics

Also starts a Pub/Sub consumer in a background thread.
"""

import os
import threading

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_shared.logging import configure_logging, get_logger
from financial_shared.tracing import configure_tracing

from financial_sentiment.config import settings
from financial_sentiment.perplexity.client import PerplexityClient
from financial_sentiment.subscribers.pubsub_consumer import SentimentEventConsumer

configure_logging(settings.log_level)
configure_tracing("financial-sentiment")
logger = get_logger(__name__)

app = FastAPI(title="Financial Sentiment Service", version="0.1.0")

_perplexity_client: PerplexityClient | None = None
_consumer: SentimentEventConsumer | None = None


class AnalyzeRequest(BaseModel):
    asset: str = Field(default="XAU")
    context: str = Field(default="", description="News or market context to analyze")
    time_horizon: str = Field(default="medium")
    current_price: float | None = None


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "sentiment"})


@app.get("/health/ready")
async def readiness() -> JSONResponse:
    if not settings.perplexity_api_key:
        return JSONResponse(
            {"status": "not_ready", "reason": "perplexity_api_key_missing"},
            status_code=503,
        )
    return JSONResponse({"status": "ready"})


@app.post("/analyze")
async def analyze(request: AnalyzeRequest) -> JSONResponse:
    """On-demand sentiment analysis for a given asset and context."""
    if _perplexity_client is None:
        raise HTTPException(status_code=503, detail="Perplexity client not initialized")

    try:
        result = await _perplexity_client.analyze_gold_sentiment(
            asset=request.asset,
            context=request.context,
            time_horizon=request.time_horizon,
            current_price=request.current_price,
        )
        return JSONResponse({
            "sentiment": result.model_dump(mode="json"),
            "ml_features": result.to_ml_features(),
        })
    except Exception as exc:
        logger.error("sentiment.analyze_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/consumer/stats")
async def consumer_stats() -> JSONResponse:
    if _consumer is None:
        return JSONResponse({"status": "consumer_not_started"})
    return JSONResponse(_consumer.get_stats())


@app.on_event("startup")
async def startup() -> None:
    global _perplexity_client, _consumer

    if settings.pubsub_emulator_host:
        os.environ["PUBSUB_EMULATOR_HOST"] = settings.pubsub_emulator_host

    _perplexity_client = PerplexityClient(
        api_key=settings.perplexity_api_key,
        model=settings.perplexity_model,
    )

    if settings.perplexity_api_key and settings.pubsub_project_id:
        _consumer = SentimentEventConsumer(
            project_id=settings.pubsub_project_id,
            input_subscription=settings.pubsub_market_events_subscription,
            output_topic=settings.pubsub_sentiment_events_topic,
            sentiment_client=_perplexity_client,
        )
        # Start consumer in background thread (Pub/Sub streaming pull is blocking)
        thread = threading.Thread(target=_consumer.start, daemon=True)
        thread.start()

    logger.info("sentiment.startup_complete")


@app.on_event("shutdown")
async def shutdown() -> None:
    global _consumer, _perplexity_client
    if _consumer:
        _consumer.stop()
    if _perplexity_client:
        await _perplexity_client.close()
    logger.info("sentiment.shutdown_complete")


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
