"""Perplexity Sonar API client with structured output enforcement.

Uses the Perplexity Sonar API (OpenAI-compatible) to:
1. Perform real-time RAG over financial news (search-augmented generation)
2. Return structured JSON output conforming to Pydantic schemas
3. Apply exponential backoff on rate limits (HTTP 429)
4. Cache results in Pinecone to avoid redundant expensive calls

The client enforces JSON output by:
  - Setting response_format={"type": "json_object"} in the API call
  - Validating the response against the Pydantic schema
  - Retrying if JSON validation fails (up to max_retries attempts)

Cost optimization note:
  - sonar-pro (~$3/1k tokens) for complex macro analysis
  - sonar (~$1/1k tokens) for simple fact lookups (via model_router)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from financial_shared.logging import get_logger
from financial_sentiment.perplexity.schemas import SentimentResult
from financial_sentiment.perplexity.prompts import (
    SYSTEM_PROMPT,
    build_gold_sentiment_prompt,
)

logger = get_logger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


class PerplexityClient:
    """Async Perplexity Sonar API client."""

    def __init__(
        self,
        api_key: str,
        model: str = "sonar-pro",
        max_tokens: int = 2000,
        temperature: float = 0.1,  # Low temperature for factual consistency
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._http = http_client or httpx.AsyncClient(timeout=60.0)

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30, jitter=2),
        reraise=True,
    )
    async def _call_api(self, messages: list[dict]) -> dict:
        """Make a raw API call to Perplexity Sonar."""
        response = await self._http.post(
            PERPLEXITY_API_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": messages,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        return response.json()

    async def analyze_gold_sentiment(
        self,
        asset: str = "XAU",
        context: str = "",
        time_horizon: str = "medium",
        current_price: float | None = None,
    ) -> SentimentResult:
        """Analyze gold sentiment with structured Pydantic output.

        Args:
            asset: Asset symbol.
            context: Additional market context to inject into the prompt.
            time_horizon: Analysis horizon.
            current_price: Current spot price for context.

        Returns:
            Validated SentimentResult Pydantic model.

        Raises:
            ValueError: If the LLM returns invalid JSON after retries.
        """
        user_prompt = build_gold_sentiment_prompt(
            asset=asset,
            context=context,
            time_horizon=time_horizon,
            current_price=current_price,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(1, 4):
            try:
                raw_response = await self._call_api(messages)
                content = raw_response["choices"][0]["message"]["content"]

                # Parse and validate against Pydantic schema
                data = json.loads(content)
                result = SentimentResult(**data)

                logger.info(
                    "perplexity.analysis_complete",
                    asset=asset,
                    direction=result.asset_sentiment.direction,
                    score=result.asset_sentiment.sentiment_score,
                    model=self._model,
                )
                return result

            except (json.JSONDecodeError, ValidationError, KeyError) as exc:
                logger.warning(
                    "perplexity.parse_failed",
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt == 3:
                    raise ValueError(
                        f"Perplexity returned invalid JSON after {attempt} attempts: {exc}"
                    ) from exc
                # Ask the model to fix the JSON in the next attempt
                messages.append({
                    "role": "assistant",
                    "content": content if 'content' in dir() else "error",
                })
                messages.append({
                    "role": "user",
                    "content": f"Your response was invalid. Error: {exc}. Return valid JSON only.",
                })

        raise ValueError("Unexpected: reached end of retry loop")

    async def close(self) -> None:
        await self._http.aclose()
