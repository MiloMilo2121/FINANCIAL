"""Milvus vector database client for historical backtesting embeddings.

Milvus is used for the historical backtesting corpus (billions of vectors)
because:
  - Self-hosted: no per-query cost for large batch workloads
  - GPU-accelerated HNSW indexing for billion-scale ANN search
  - Supports complex metadata filtering (date range, asset class)

Used for:
  - Finding historically similar market regimes for analogical reasoning
  - Backtesting: "In which past periods were conditions most like today?"
  - Training data retrieval for fine-tuning ML models
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

try:
    from pymilvus import (
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False

from financial_shared.logging import get_logger

logger = get_logger(__name__)

_EMBEDDING_DIM = 768
_COLLECTION_SCHEMA_FIELDS = [
    ("id", DataType.INT64, True),       # Primary key
    ("event_date", DataType.VARCHAR),   # YYYY-MM-DD
    ("asset", DataType.VARCHAR),        # e.g. "XAU"
    ("embedding", DataType.FLOAT_VECTOR, _EMBEDDING_DIM),
    ("metadata_json", DataType.VARCHAR),
] if MILVUS_AVAILABLE else []


class MilvusHistoricalStore:
    """Milvus-backed vector store for historical market regime embeddings."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "historical_embeddings",
    ) -> None:
        self._collection_name = collection_name
        self._collection: Any = None

        if not MILVUS_AVAILABLE:
            logger.warning("milvus.unavailable", reason="pymilvus not installed")
            return

        try:
            connections.connect("default", host=host, port=port)
            self._ensure_collection()
            logger.info("milvus.connected", host=host, port=port)
        except Exception as exc:
            logger.error("milvus.connection_failed", error=str(exc))

    def _ensure_collection(self) -> None:
        """Create collection with HNSW index if it doesn't exist."""
        if utility.has_collection(self._collection_name):
            self._collection = Collection(self._collection_name)
            self._collection.load()
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="event_date", dtype=DataType.VARCHAR, max_length=10),
            FieldSchema(name="asset", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=_EMBEDDING_DIM),
            FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=4096),
        ]
        schema = CollectionSchema(fields=fields, description="Historical market regime embeddings")
        self._collection = Collection(name=self._collection_name, schema=schema)

        # HNSW index: fast approximate nearest neighbor search
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200},
        }
        self._collection.create_index("embedding", index_params)
        self._collection.load()
        logger.info("milvus.collection_created", name=self._collection_name)

    def insert(
        self,
        embeddings: np.ndarray,
        event_dates: list[str],
        assets: list[str],
        metadata_list: list[dict],
    ) -> list[int]:
        """Insert a batch of historical embeddings.

        Args:
            embeddings: (n, 768) array of event embeddings.
            event_dates: List of YYYY-MM-DD strings.
            assets: List of asset symbols.
            metadata_list: List of metadata dicts per record.

        Returns:
            List of auto-assigned integer IDs.
        """
        if self._collection is None:
            return []

        data = [
            event_dates,
            assets,
            embeddings.tolist(),
            [json.dumps(m, default=str) for m in metadata_list],
        ]
        result = self._collection.insert(data)
        return list(result.primary_keys)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        asset_filter: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """Search for historically similar market regimes.

        Args:
            query_embedding: Query vector (768,).
            top_k: Number of results to return.
            asset_filter: Optional asset symbol filter (e.g. "XAU").
            date_from: Optional start date filter (YYYY-MM-DD).
            date_to: Optional end date filter (YYYY-MM-DD).

        Returns:
            List of result dicts with 'score', 'event_date', 'asset', 'metadata'.
        """
        if self._collection is None:
            return []

        # Build expression filter
        expr_parts = []
        if asset_filter:
            expr_parts.append(f'asset == "{asset_filter}"')
        if date_from:
            expr_parts.append(f'event_date >= "{date_from}"')
        if date_to:
            expr_parts.append(f'event_date <= "{date_to}"')
        expr = " && ".join(expr_parts) if expr_parts else None

        search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
        results = self._collection.search(
            data=[query_embedding.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["event_date", "asset", "metadata_json"],
        )

        hits = []
        for hit in results[0]:
            hits.append({
                "score": float(hit.score),
                "event_date": hit.entity.get("event_date"),
                "asset": hit.entity.get("asset"),
                "metadata": json.loads(hit.entity.get("metadata_json", "{}")),
            })
        return hits
