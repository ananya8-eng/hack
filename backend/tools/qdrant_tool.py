"""
Direct Qdrant Cloud access for vector search.

Embeddings are produced by the embedding server; this module only queries stored vectors.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _build_qdrant_filter(flat: dict) -> Any:
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    if not flat:
        return None
    conditions = [
        FieldCondition(key=k, match=MatchValue(value=v))
        for k, v in flat.items()
        if v is not None and k != "document"
    ]
    if not conditions:
        return None
    return Filter(must=conditions)


def _format_hits(results: list) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for point in results:
        payload = point.payload or {}
        meta = dict(payload)
        document = str(meta.pop("document", "") or "")
        formatted.append(
            {
                "document": document,
                "metadata": meta,
                "score": float(point.score or 0.0),
                "id": str(point.id),
            }
        )
    return formatted


class QdrantVectorClient:
    """Singleton client for semantic search against Qdrant Cloud."""

    _instance: QdrantVectorClient | None = None

    def __new__(cls) -> QdrantVectorClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
            cls._instance._collection = ""
            cls._instance._ready = False
        return cls._instance

    def is_configured(self) -> bool:
        return bool(get_settings().qdrant_url.strip())

    def initialize(self) -> None:
        if self._ready:
            return
        settings = get_settings()
        url = settings.qdrant_url.strip()
        if not url:
            return
        from qdrant_client import QdrantClient

        api_key = settings.qdrant_api_key.strip() or None
        self._client = QdrantClient(url=url, api_key=api_key)
        self._collection = settings.qdrant_collection.strip() or "documents"
        self._ready = True
        logger.info("Qdrant search client ready (collection=%s).", self._collection)

    def search(
        self,
        query_vector: list[float],
        *,
        limit: int,
        metadata_filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("QDRANT_URL is not set on the backend.")
        self.initialize()
        if self._client is None:
            raise RuntimeError("Qdrant client failed to initialize.")

        flat = metadata_filter or {}
        qdrant_filter = _build_qdrant_filter(flat)

        # qdrant-client >=1.12 uses query_points; older releases expose search().
        if hasattr(self._client, "query_points"):
            response = self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
            )
            hits = response.points or []
        else:
            hits = self._client.search(
                collection_name=self._collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
            )
        return _format_hits(hits)


qdrant_client = QdrantVectorClient()
