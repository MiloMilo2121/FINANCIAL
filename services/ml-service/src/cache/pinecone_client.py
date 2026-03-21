"""Pinecone vector database client for semantic caching.

Two use cases:
  1. ML prediction cache: If a new prediction request is semantically
     similar (cosine > 0.92) to a recent cached prediction, return the
     cached result without invoking LSTM/XGBoost. Reduces inference cost
     by 30-50% per the architecture spec.

  2. Sentiment deduplication: News articles covering the same event
     from different outlets are deduplicated using semantic similarity,
     avoiding redundant Perplexity API calls.

Pinecone is chosen for real-time use because:
  - Fully managed (no infrastructure to maintain)
  - <50ms p99 latency for ANN search
  - Supports metadata filtering (by asset, timeframe, source)
  - Real-time index updates (vs Milvus which requires batch indexing)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import numpy as np

try:
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

from financial_shared.logging import get_logger

logger = get_logger(__name__)

_EMBEDDING_DIM = 768  # BERT CLS token dimension


class PineconeSemanticCache:
    """Pinecone-backed semantic similarity cache.

    Falls back to an in-memory dict cache if Pinecone is unavailable
    (e.g., during local development without API key).
    """

    def __init__(
        self,
        api_key: str,
        index_name: str,
        similarity_threshold: float = 0.92,
        namespace: str = "predictions",
    ) -> None:
        self._threshold = similarity_threshold
        self._namespace = namespace
        self._fallback_cache: dict[str, Any] = {}  # Dev fallback

        if not PINECONE_AVAILABLE or not api_key:
            logger.warning(
                "pinecone.unavailable",
                reason="pinecone-client not installed or no API key",
            )
            self._pc = None
            self._index = None
            return

        try:
            self._pc = Pinecone(api_key=api_key)
            self._ensure_index(index_name)
            self._index = self._pc.Index(index_name)
            logger.info("pinecone.connected", index=index_name)
        except Exception as exc:
            logger.error("pinecone.connection_failed", error=str(exc))
            self._pc = None
            self._index = None

    def _ensure_index(self, index_name: str) -> None:
        """Create Pinecone index if it doesn't exist."""
        existing = [i.name for i in self._pc.list_indexes()]
        if index_name not in existing:
            self._pc.create_index(
                name=index_name,
                dimension=_EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            logger.info("pinecone.index_created", index=index_name)

    def lookup(
        self,
        query_embedding: np.ndarray,
        metadata_filter: dict | None = None,
    ) -> dict | None:
        """Look up a semantically similar cached result.

        Returns cached payload dict if similarity >= threshold, else None.
        """
        if self._index is None:
            # Fallback: check dict cache (exact match only)
            key = hashlib.md5(query_embedding.tobytes()).hexdigest()
            return self._fallback_cache.get(key)

        try:
            results = self._index.query(
                vector=query_embedding.tolist(),
                top_k=1,
                include_metadata=True,
                filter=metadata_filter or {},
                namespace=self._namespace,
            )
            matches = results.get("matches", [])
            if matches and matches[0]["score"] >= self._threshold:
                logger.debug(
                    "pinecone.cache_hit",
                    score=matches[0]["score"],
                    threshold=self._threshold,
                )
                return json.loads(matches[0]["metadata"].get("payload", "{}"))
        except Exception as exc:
            logger.warning("pinecone.lookup_failed", error=str(exc))

        return None

    def store(
        self,
        embedding: np.ndarray,
        payload: dict,
        vector_id: str,
        metadata: dict | None = None,
    ) -> None:
        """Store a prediction result with its embedding vector.

        Args:
            embedding: Query embedding vector (768-dim).
            payload: Prediction result to cache.
            vector_id: Unique ID for the vector.
            metadata: Additional filterable metadata (asset, timeframe).
        """
        full_metadata = {
            "payload": json.dumps(payload, default=str),
            "cached_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        }

        if self._index is None:
            # Fallback to in-memory
            key = hashlib.md5(embedding.tobytes()).hexdigest()
            self._fallback_cache[key] = payload
            return

        try:
            self._index.upsert(
                vectors=[{
                    "id": vector_id,
                    "values": embedding.tolist(),
                    "metadata": full_metadata,
                }],
                namespace=self._namespace,
            )
        except Exception as exc:
            logger.warning("pinecone.store_failed", error=str(exc))

    def clear_namespace(self) -> None:
        """Delete all vectors in the cache namespace (for testing)."""
        if self._index:
            try:
                self._index.delete(delete_all=True, namespace=self._namespace)
            except Exception as exc:
                logger.warning("pinecone.clear_failed", error=str(exc))
