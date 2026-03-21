"""Tests for data connectors using pytest-httpx for HTTP mocking."""

from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio

from financial_ingestion.connectors.alpha_vantage import AlphaVantageConnector
from financial_ingestion.connectors.metalpriceapi import MetalpriceAPIConnector
from financial_ingestion.schemas.market_event import AssetClass


@pytest.fixture
def mock_http():
    """Provides a transport mock for httpx."""
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda request: None))


class TestAlphaVantageConnector:
    @pytest.mark.asyncio
    async def test_normalize_valid_record(self):
        connector = AlphaVantageConnector(
            http_client=httpx.AsyncClient(),
            api_key="demo",
        )
        raw = {
            "asset": "XAU",
            "date": "2024-01-15",
            "open": "2020.50",
            "high": "2035.00",
            "low": "2015.00",
            "close": "2030.00",
            "volume": None,
        }
        event = connector.normalize(raw)
        assert event.asset == "XAU"
        assert event.source == "alpha_vantage"
        assert event.asset_class == AssetClass.METAL
        assert event.close == pytest.approx(2030.0)
        assert event.price_usd == pytest.approx(2030.0)
        assert event.interval == "1d"
        assert event.timestamp.tzinfo is not None

    @pytest.mark.asyncio
    async def test_normalize_uppercase_asset(self):
        connector = AlphaVantageConnector(
            http_client=httpx.AsyncClient(),
            api_key="demo",
        )
        raw = {
            "asset": "xau",  # lowercase
            "date": "2024-01-15",
            "open": "2020.50",
            "high": "2035.00",
            "low": "2015.00",
            "close": "2030.00",
            "volume": None,
        }
        event = connector.normalize(raw)
        assert event.asset == "XAU"  # Should be uppercased by validator


class TestMetalpriceAPIConnector:
    @pytest.mark.asyncio
    async def test_normalize_tick_record(self):
        connector = MetalpriceAPIConnector(
            http_client=httpx.AsyncClient(),
            api_key="test",
        )
        raw = {
            "asset": "XAU",
            "timestamp": "2024-01-15T10:30:00+00:00",
            "price_usd": 2035.50,
            "base": "USD",
        }
        event = connector.normalize(raw)
        assert event.asset == "XAU"
        assert event.price_usd == pytest.approx(2035.50)
        assert event.interval == "tick"
        assert event.currency == "USD"


class TestMarketEventSchema:
    def test_event_serializes_to_pubsub_payload(self):
        from financial_ingestion.schemas.market_event import MarketEvent, AssetClass
        event = MarketEvent(
            timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            source="test",
            asset="XAU",
            asset_class=AssetClass.METAL,
            price_usd=2030.0,
            currency="USD",
        )
        payload = event.to_pubsub_payload()
        assert payload["asset"] == "XAU"
        assert payload["source"] == "test"
        assert "event_id" in payload
        assert "timestamp" in payload

    def test_naive_timestamp_gets_utc(self):
        from financial_ingestion.schemas.market_event import MarketEvent, AssetClass
        naive_ts = datetime(2024, 1, 15, 10, 0, 0)  # No tzinfo
        event = MarketEvent(
            timestamp=naive_ts,
            source="test",
            asset="XAG",
            asset_class=AssetClass.METAL,
        )
        assert event.timestamp.tzinfo is not None
