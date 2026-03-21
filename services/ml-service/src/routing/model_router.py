"""Smart model routing for cost optimization.

Routes prediction requests to the appropriate model tier:
  1. Pinecone semantic cache hit (cosine > 0.92): return cached result (~0ms)
  2. Lightweight rule-based model: simple regime detection (<5ms)
  3. Full LSTM-XGBoost hybrid ensemble: complete inference (~200ms)
  4. Full multimodal LSTM-XGBoost + BERT + CrossModalAttention (~500ms)

This routing strategy reduces Perplexity API calls and GPU inference
by 30-50% according to the architecture spec.

Routing criteria:
  - Cache hit: use cache
  - Simple/repetitive query (low complexity score): lightweight model
  - High GPR index or novel news pattern: full multimodal pipeline
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import numpy as np

from financial_shared.logging import get_logger

logger = get_logger(__name__)


class ModelTier(str, Enum):
    CACHE = "cache"
    LIGHTWEIGHT = "lightweight"
    HYBRID_ENSEMBLE = "hybrid_ensemble"
    FULL_MULTIMODAL = "full_multimodal"


class PredictionRouter:
    """Routes prediction requests to the appropriate model tier."""

    def __init__(
        self,
        cache,                   # PineconeSemanticCache instance
        hybrid_ensemble=None,    # HybridEnsemble instance
        multimodal_model=None,   # MultimodalFusion instance
        gpr_threshold: float = 200.0,  # GPR index level above which → full multimodal
        cache_threshold: float = 0.92,
    ) -> None:
        self._cache = cache
        self._hybrid = hybrid_ensemble
        self._multimodal = multimodal_model
        self._gpr_threshold = gpr_threshold
        self._cache_threshold = cache_threshold
        self._request_count = 0
        self._cache_hit_count = 0

    def route(
        self,
        query_embedding: np.ndarray,
        gpr_index: float = 0.0,
        has_news: bool = False,
        metadata_filter: dict | None = None,
    ) -> ModelTier:
        """Determine which model tier to use for this request.

        Args:
            query_embedding: Embedding of the current prediction query.
            gpr_index: Current GPR index value (0-1000 scale).
            has_news: Whether novel news events are present.
            metadata_filter: Pinecone metadata filter for cache lookup.

        Returns:
            The ModelTier to use.
        """
        self._request_count += 1

        # Check semantic cache first
        if self._cache:
            cached = self._cache.lookup(query_embedding, metadata_filter)
            if cached is not None:
                self._cache_hit_count += 1
                logger.debug(
                    "router.cache_hit",
                    cache_hit_rate=self.cache_hit_rate,
                )
                return ModelTier.CACHE

        # High geopolitical risk or novel news → full multimodal
        if gpr_index > self._gpr_threshold or (has_news and self._multimodal is not None):
            return ModelTier.FULL_MULTIMODAL

        # Default to hybrid ensemble (LSTM + XGBoost)
        if self._hybrid is not None:
            return ModelTier.HYBRID_ENSEMBLE

        return ModelTier.LIGHTWEIGHT

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of requests served from cache."""
        if self._request_count == 0:
            return 0.0
        return self._cache_hit_count / self._request_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_requests": self._request_count,
            "cache_hits": self._cache_hit_count,
            "cache_hit_rate_pct": round(self.cache_hit_rate * 100, 2),
            "estimated_cost_reduction_pct": round(self.cache_hit_rate * 50, 2),
        }
