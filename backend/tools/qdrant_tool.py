"""
Direct Qdrant Cloud access for vector search.

Embeddings are produced by the embedding server; this module only queries stored vectors.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Payload fields used in filters during RAG / map-reduce (must be indexed in Qdrant).
_PAYLOAD_INDEX_SPECS: dict[str, str] = {
    "company": "keyword",
    "section": "keyword",
    "section_title": "keyword",
    "chunk_id": "keyword",
    "chunk_index": "integer",
}


def _metadata_matches_filter(metadata: dict | None, flat: dict) -> bool:
    if not flat:
        return True
    metadata = metadata or {}
    return all(metadata.get(k) == v for k, v in flat.items())


def _ensure_payload_indexes(client: Any, collection: str) -> None:
    from qdrant_client.models import PayloadSchemaType

    schema_types = {
        "keyword": PayloadSchemaType.KEYWORD,
        "integer": PayloadSchemaType.INTEGER,
    }
    for field, kind in _PAYLOAD_INDEX_SPECS.items():
        try:
            client.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=schema_types[kind],
                wait=True,
            )
            logger.info("Qdrant payload index ready: %s (%s).", field, kind)
        except Exception as exc:
            message = str(exc).lower()
            if "already exists" in message or "already indexed" in message:
                continue
            logger.warning("Qdrant payload index %s skipped: %s", field, exc)


def _is_missing_index_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "index required" in text and "not found" in text


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
        document = str(meta.pop("document", "") or meta.pop("text", "") or "")
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
        _ensure_payload_indexes(self._client, self._collection)
        self._ready = True
        logger.info("Qdrant search client ready (collection=%s).", self._collection)

    def _query_points(
        self,
        query_vector: list[float],
        *,
        limit: int,
        qdrant_filter: Any,
    ) -> list:
        if hasattr(self._client, "query_points"):
            response = self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
            )
            return list(response.points or [])
        return self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=limit,
            query_filter=qdrant_filter,
        )

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

        try:
            hits = self._query_points(
                query_vector, limit=limit, qdrant_filter=qdrant_filter
            )
            return _format_hits(hits)
        except Exception as exc:
            if not flat or not _is_missing_index_error(exc):
                raise
            logger.warning(
                "Qdrant filter indexes missing; retrying search without filter "
                "and matching payload in-app for: %s",
                list(flat.keys()),
            )
            fetch_limit = min(max(limit * 10, 50), 200)
            hits = self._query_points(
                query_vector, limit=fetch_limit, qdrant_filter=None
            )
            formatted = _format_hits(hits)
            filtered = [
                row
                for row in formatted
                if _metadata_matches_filter(row.get("metadata"), flat)
            ]
            return filtered[:limit]


qdrant_client = QdrantVectorClient()
