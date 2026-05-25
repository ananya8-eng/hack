"""
Vector store: indexing via embedding server (/embed → Qdrant), search via Qdrant Cloud
from the backend (query vector from embedding server /query).
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from backend.tools.embedding_tool import (
    embedding_manager,
    get_mock_embedding,
    register_local_chunks,
)

logger = logging.getLogger(__name__)


def _flatten_where(where: dict | None) -> dict:
    """Normalize filters to flat {field: value} for Qdrant payload matching."""
    if not where:
        return {}
    if "$and" in where and isinstance(where["$and"], list):
        flat: dict = {}
        for sub in where["$and"]:
            if isinstance(sub, dict):
                for k, v in sub.items():
                    if not isinstance(v, dict):
                        flat[k] = v
        return flat
    return {k: v for k, v in where.items() if not isinstance(v, dict)}


def _metadata_matches_where(metadata: dict | None, flat_where: dict) -> bool:
    if not flat_where:
        return True
    metadata = metadata or {}
    return all(metadata.get(k) == v for k, v in flat_where.items())


def _search_in_memory(
    query_text: str,
    *,
    n_results: int,
    flat_where: dict,
    cache: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not cache:
        return []

    query_vec = np.array(get_mock_embedding(query_text))
    query_norm = np.linalg.norm(query_vec)
    scored: list[dict[str, Any]] = []

    for item in cache:
        if flat_where and not _metadata_matches_where(item.get("metadata"), flat_where):
            continue
        emb = item.get("embedding") or []
        item_vec = np.array(emb if emb else get_mock_embedding(item["document"]))
        item_norm = np.linalg.norm(item_vec)
        score = (
            float(np.dot(query_vec, item_vec) / (query_norm * item_norm))
            if query_norm > 0 and item_norm > 0
            else 0.0
        )
        scored.append(
            {
                "document": item["document"],
                "metadata": item.get("metadata", {}),
                "score": score,
                "id": item["id"],
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:n_results]


class QdrantVectorStore:
    """Upsert and query filing chunks in Qdrant Cloud (remote) or in-memory (dev)."""

    def __init__(self) -> None:
        self._cache: list[dict[str, Any]] = []
        embedding_manager.initialize()
        self._use_qdrant = embedding_manager.uses_qdrant_remote()
        if self._use_qdrant:
            logger.info(
                "Vector store: embed via embedding service, search via Qdrant Cloud."
            )
        elif embedding_manager.use_remote:
            logger.warning(
                "Embedding service is in vectors mode (not qdrant). "
                "Set EMBEDDING_SERVICE_MODE=qdrant for Qdrant Cloud storage."
            )
        else:
            logger.info(
                "Vector store: in-memory only (set EMBEDDING_SERVICE_URL for Qdrant Cloud)."
            )

    def add_chunks(
        self,
        chunks: list[str],
        metadata_list: list[dict],
        ids: list[str],
    ) -> None:
        if not chunks:
            return

        if self._use_qdrant:
            point_ids = embedding_manager.upsert_chunks(chunks, metadata_list, ids)
            for i, chunk in enumerate(chunks):
                doc_id = ids[i]
                meta = metadata_list[i] if i < len(metadata_list) else {}
                qdrant_id = point_ids[i] if i < len(point_ids) else doc_id
                row = {
                    "id": doc_id,
                    "qdrant_id": qdrant_id,
                    "document": chunk,
                    "embedding": [],
                    "metadata": meta,
                }
                existing = next((r for r in self._cache if r["id"] == doc_id), None)
                if existing:
                    existing.update(row)
                else:
                    self._cache.append(row)
            logger.info("Upserted %s chunks to Qdrant Cloud.", len(chunks))
            return

        if embedding_manager.use_remote:
            embeddings = embedding_manager.get_embeddings(chunks)
        else:
            embeddings = [get_mock_embedding(c) for c in chunks]
        register_local_chunks(chunks, metadata_list, ids, embeddings)

        for i, chunk in enumerate(chunks):
            doc_id = ids[i]
            meta = metadata_list[i] if i < len(metadata_list) else {}
            emb = embeddings[i] if i < len(embeddings) else []
            row = {
                "id": doc_id,
                "document": chunk,
                "embedding": emb,
                "metadata": meta,
            }
            existing = next((r for r in self._cache if r["id"] == doc_id), None)
            if existing:
                existing.update(row)
            else:
                self._cache.append(row)
        logger.info("Indexed %s chunks in local dev cache.", len(chunks))

    def query_similar_chunks(
        self,
        query_text: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        flat_where = _flatten_where(where)

        if self._use_qdrant:
            try:
                results = embedding_manager.search_chunks(
                    query_text,
                    n_results=n_results,
                    where=flat_where,
                )
                if results:
                    return results
            except Exception as exc:
                logger.warning("Qdrant search failed: %s", exc)

            return _search_in_memory(
                query_text,
                n_results=n_results,
                flat_where=flat_where,
                cache=self._cache,
            )

        if embedding_manager.use_remote:
            try:
                query_emb = embedding_manager.get_embedding(query_text)
                from backend.tools.embedding_tool import _search_local_cache

                return _search_local_cache(
                    query_emb,
                    limit=n_results,
                    metadata_filter=flat_where,
                )
            except Exception as exc:
                logger.warning("Remote vector search failed: %s", exc)

        return _search_in_memory(
            query_text,
            n_results=n_results,
            flat_where=flat_where,
            cache=self._cache,
        )


vector_store = QdrantVectorStore()

# Backward-compatible alias used across the codebase
chromadb_manager = vector_store
