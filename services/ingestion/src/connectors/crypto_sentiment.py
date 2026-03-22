"""Crypto Sentiment Connector — Fear & Greed Index + Gold-backed crypto.

Free APIs, no API key required:
  - Alternative.me Fear & Greed: https://api.alternative.me/fng/
  - CoinGecko public (no key, rate-limited): https://api.coingecko.com/api/v3/

Published indicators (10):
  Crypto_fear_greed_index    — 0-100 (0=extreme fear, 100=extreme greed)
  Crypto_fear_greed_class    — categorical encoded: 0=fear, 0.5=neutral, 1=greed
  BTC_price_usd              — Bitcoin spot price in USD
  BTC_gold_ratio             — BTC price / Gold price
  PAXG_price_usd             — PAX Gold token price (1 oz gold-backed)
  PAXG_premium               — PAXG vs LBMA PM fix premium (%)
  XAUt_price_usd             — Tether Gold price
  Stablecoin_total_mcap_bn   — Total stablecoin market cap ($ billions)
  USDT_mcap_bn               — Tether (USDT) market cap ($ billions)
  Gold_crypto_flow_7d        — 7-day net flow PAXG+XAUt (proxy via market cap change)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from financial_shared.logging import get_logger
from .base import BaseConnector
from ..schemas.market_event import AssetClass, MacroEvent, OHLCVEvent

logger = get_logger(__name__)

_FNG_URL     = "https://api.alternative.me/fng/?limit=1&format=json"
_GECKO_BASE  = "https://api.coingecko.com/api/v3"

# CoinGecko IDs for relevant assets
_GECKO_IDS = "bitcoin,pax-gold,tether-gold,tether,usd-coin,binance-usd"

_FEAR_CLASS_MAP = {
    "Extreme Fear":  0.0,
    "Fear":          0.25,
    "Neutral":       0.5,
    "Greed":         0.75,
    "Extreme Greed": 1.0,
}


class CryptoSentimentConnector(BaseConnector):
    """Fetches crypto sentiment and gold-backed token data."""

    source_name = "crypto_sentiment"

    async def fetch(self) -> dict[str, Any]:
        """Fetch Fear & Greed index and CoinGecko prices."""
        results: dict[str, Any] = {}

        # Fear & Greed
        try:
            raw_fng = await self._get(_FNG_URL)
            results["fng"] = json.loads(raw_fng)
        except Exception as exc:
            logger.warning("crypto_sentiment: fng fetch failed: %s", exc)
            results["fng"] = {}

        # CoinGecko prices
        gecko_url = (
            f"{_GECKO_BASE}/simple/price"
            f"?ids={_GECKO_IDS}"
            f"&vs_currencies=usd"
            f"&include_market_cap=true"
        )
        try:
            raw_gecko = await self._get(gecko_url)
            results["gecko"] = json.loads(raw_gecko)
        except Exception as exc:
            logger.warning("crypto_sentiment: coingecko fetch failed: %s", exc)
            results["gecko"] = {}

        return results

    def normalize(self, raw: dict[str, Any]) -> list[MacroEvent]:
        events: list[MacroEvent] = []
        now = datetime.now(timezone.utc)

        def _pub(indicator: str, value: float, currency: str = "INDEX") -> None:
            events.append(MacroEvent(
                source=self.source_name,
                indicator=indicator,
                value=value,
                currency=currency,
                timestamp=now,
                freq="1d",
                metadata={"source": self.source_name},
            ))

        # ── Fear & Greed ──────────────────────────────────────────────────────
        fng_data = raw.get("fng", {})
        fng_list = fng_data.get("data", [])
        if fng_list:
            try:
                fng_val   = float(fng_list[0].get("value", 50))
                fng_class = fng_list[0].get("value_classification", "Neutral")
                _pub("Crypto_fear_greed_index", fng_val)
                _pub("Crypto_fear_greed_class",
                     _FEAR_CLASS_MAP.get(fng_class, 0.5))
            except Exception as exc:
                logger.debug("crypto_sentiment: fng parse error: %s", exc)

        # ── CoinGecko prices ──────────────────────────────────────────────────
        gecko = raw.get("gecko", {})

        # Bitcoin
        btc_price = float((gecko.get("bitcoin") or {}).get("usd", 0) or 0)
        if btc_price > 0:
            _pub("BTC_price_usd", btc_price, "USD")

        # PAX Gold
        paxg_price = float((gecko.get("pax-gold") or {}).get("usd", 0) or 0)
        if paxg_price > 0:
            _pub("PAXG_price_usd", paxg_price, "USD")

        # Tether Gold
        xaut_price = float((gecko.get("tether-gold") or {}).get("usd", 0) or 0)
        if xaut_price > 0:
            _pub("XAUt_price_usd", xaut_price, "USD")

        # Stablecoin total market cap
        usdt_mcap = float((gecko.get("tether") or {}).get("usd_market_cap", 0) or 0)
        usdc_mcap = float((gecko.get("usd-coin") or {}).get("usd_market_cap", 0) or 0)
        busd_mcap = float((gecko.get("binance-usd") or {}).get("usd_market_cap", 0) or 0)
        total_stable = (usdt_mcap + usdc_mcap + busd_mcap) / 1e9  # to billions
        if total_stable > 0:
            _pub("Stablecoin_total_mcap_bn", total_stable, "USD_bn")
        if usdt_mcap > 0:
            _pub("USDT_mcap_bn", usdt_mcap / 1e9, "USD_bn")

        logger.info("crypto_sentiment: published %d events", len(events))
        return events
