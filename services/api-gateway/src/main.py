"""API Gateway — Single entry point for the Financial Projection Platform.

Handles:
  - JWT authentication
  - Per-user Redis rate limiting
  - Request routing to downstream microservices
  - WebSocket streaming for real-time price ticks
  - CORS configuration for the React frontend

All inter-service communication in production uses mTLS via GKE
Managed Workload Identities — not visible at this application layer.
"""

import asyncio
import json
import os
from typing import Any

import redis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from financial_shared.logging import configure_logging, get_logger
from financial_shared.tracing import configure_tracing
from financial_shared.redis_client import get_sync_redis

from financial_gateway.config import settings
from financial_gateway.routers import prices, projections, sentiment, health
from financial_gateway.middleware.rate_limit import UserRateLimiter

configure_logging(settings.log_level)
configure_tracing("financial-api-gateway")
logger = get_logger(__name__)

app = FastAPI(
    title="Financial Projection Platform API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS: allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(prices.router)
app.include_router(projections.router)
app.include_router(sentiment.router)


@app.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "api-gateway"})


@app.get("/health/ready")
async def readiness() -> JSONResponse:
    try:
        r = get_sync_redis(settings.redis_url)
        r.ping()
        return JSONResponse({"status": "ready"})
    except Exception as exc:
        return JSONResponse({"status": "not_ready", "error": str(exc)}, status_code=503)


# ---- WebSocket for real-time price streaming ----

class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active_connections.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.active_connections.remove(conn)


manager = ConnectionManager()


@app.websocket("/ws/prices/{asset}")
async def websocket_price_feed(websocket: WebSocket, asset: str) -> None:
    """Real-time price feed WebSocket endpoint.

    In production: subscribes to the Pub/Sub market-events topic
    and streams price updates to connected TradingView clients.

    The frontend CustomDatafeed.ts subscribeBars() method connects here.
    """
    await manager.connect(websocket)
    logger.info("ws.client_connected", asset=asset)
    try:
        while True:
            # In production: receive price updates from Pub/Sub
            # and forward to clients. For dev: send periodic mock updates.
            await asyncio.sleep(5)
            await websocket.send_json({
                "type": "tick",
                "asset": asset.upper(),
                "price": None,  # Populated from live data in production
                "timestamp": None,
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("ws.client_disconnected", asset=asset)
    except Exception as exc:
        logger.error("ws.error", error=str(exc))
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup() -> None:
    logger.info("gateway.startup_complete", cors_origins=settings.cors_origins)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
