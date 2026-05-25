import hashlib
import logging
from typing import Any
from urllib.parse import urljoin

import numpy as np
import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _as_flat_embedding(vector) -> list:
    """Return a single flat embedding vector (list of floats)."""
    if hasattr(vector, "tolist"):
        data = vector.tolist()
    else:
        data = list(vector)
    while data and isinstance(data[0], list):
        if len(data) != 1:
            break
        data = data[0]
    return data


def get_mock_embedding(text: str, dim: int | None = None) -> list:
    """
    Generates deterministic, normalized mock embeddings using a SHA-256 hash seed.
    """
    if dim is None:
        dim = get_settings().embedding_dimension
    h = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(h[:4], byteorder="big") % (2**32)

    rng = np.random.default_rng(seed)
    vec = rng.normal(0.0, 1.0, dim)

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def _normalize_service_url(base: str) -> str:
    return base.rstrip("/")


def _normalize_embed_path(path: str) -> str:
    cleaned = (path or "/embed").strip()
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned


def _resolve_body_format(explicit: str, embed_path: str) -> str:
    normalized = explicit.strip().lower()
    if normalized in ("text", "texts"):
        return normalized
    if _normalize_embed_path(embed_path) == "/embed":
        return "text"
    return "texts"


def _request_headers(base_url: str, api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    if "ngrok" in base_url.lower():
        headers["ngrok-skip-browser-warning"] = "true"
    return headers


def _vectors_from_payload(payload: dict, *, expected_count: int) -> list[list[float]]:
    if not isinstance(payload, dict):
        raise RuntimeError("Embedding service returned non-JSON object")

    if "embeddings" in payload:
        embeddings = payload.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            if isinstance(embeddings[0], list):
                vectors = [_as_flat_embedding(row) for row in embeddings]
            else:
                vectors = [_as_flat_embedding(embeddings)]
            if len(vectors) == expected_count:
                return vectors

    for key in ("embedding", "vector"):
        value = payload.get(key)
        if value is not None:
            vectors = [_as_flat_embedding(value)]
            if expected_count == 1:
                return vectors

    if (
        payload.get("success")
        and "embedding_size" in payload
        and "id" in payload
        and "embedding" not in payload
        and "vector" not in payload
    ):
        raise RuntimeError(
            "Embedding service stored in Qdrant but did not return a vector. "
            "Use EMBEDDING_SERVICE_MODE=qdrant; index via POST /embed and query via POST /query."
        )

    raise RuntimeError(
        "Embedding service returned unrecognized payload keys: "
        f"{sorted(payload.keys())}"
    )


def _post_json(
    *,
    url: str,
    headers: dict[str, str],
    body: dict,
    timeout: int,
) -> dict:
    response = requests.post(url, json=body, headers=headers, timeout=timeout)
    if response.status_code >= 400:
        detail = response.text[:500]
        raise RuntimeError(
            f"Embedding service returned {response.status_code}: {detail}"
        )
    return response.json()


def _service_url(base_url: str, path: str) -> str:
    normalized = _normalize_embed_path(path)
    return urljoin(_normalize_service_url(base_url) + "/", normalized.lstrip("/"))


def _fetch_remote_embeddings(
    texts: list[str],
    *,
    base_url: str,
    embed_path: str,
    body_format: str,
    api_key: str,
    timeout: int,
    metadata_list: list[dict] | None = None,
) -> list[list[float]]:
    path = _normalize_embed_path(embed_path)
    url = _service_url(base_url, path)
    headers = _request_headers(base_url, api_key)
    fmt = _resolve_body_format(body_format, path)
    metas = metadata_list or [{} for _ in texts]

    if fmt == "texts":
        payload = _post_json(
            url=url,
            headers=headers,
            body={"texts": texts},
            timeout=timeout,
        )
        return _vectors_from_payload(payload, expected_count=len(texts))

    vectors: list[list[float]] = []
    for text, meta in zip(texts, metas):
        payload = _post_json(
            url=url,
            headers=headers,
            body={"text": text, "metadata": meta},
            timeout=timeout,
        )
        batch = _vectors_from_payload(payload, expected_count=1)
        vectors.append(batch[0])
    return vectors


def _is_qdrant_upsert_response(payload: dict) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("success") is True
        and "id" in payload
        and "embedding_size" in payload
    )


def _remote_upsert_one(
    *,
    text: str,
    metadata: dict,
    base_url: str,
    embed_path: str,
    api_key: str,
    timeout: int,
) -> str:
    url = _service_url(base_url, embed_path)
    headers = _request_headers(base_url, api_key)
    payload = _post_json(
        url=url,
        headers=headers,
        body={"text": text, "metadata": metadata},
        timeout=timeout,
    )
    if not _is_qdrant_upsert_response(payload):
        raise RuntimeError(
            "Expected Qdrant upsert response {success, id, embedding_size}; "
            f"got keys {sorted(payload.keys())}"
        )
    return str(payload["id"])


def _normalize_query_path(path: str) -> str:
    cleaned = (path or "/query").strip()
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned


def _fetch_query(
    text: str,
    *,
    base_url: str,
    query_path: str,
    api_key: str,
    timeout: int,
) -> list[float]:
    """Return a query vector from the embedding server POST /query (no Qdrant write)."""
    url = _service_url(base_url, _normalize_query_path(query_path))
    headers = _request_headers(base_url, api_key)
    payload = _post_json(
        url=url,
        headers=headers,
        body={"text": text},
        timeout=timeout,
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        raise RuntimeError(f"Query embedding failed: {payload}")
    if "embedding" not in payload:
        raise RuntimeError(
            "Embedding server /query must return {success, embedding}. "
            f"Got keys: {sorted(payload.keys())}"
        )
    return _as_flat_embedding(payload["embedding"])


# Backward-compatible alias for tests and callers
_fetch_encode = _fetch_query


_local_chunk_cache: list[dict[str, Any]] = []


def register_local_chunks(
    chunks: list[str],
    metadata_list: list[dict],
    ids: list[str],
    embeddings: list[list[float]] | None = None,
) -> None:
    """Mirror indexed chunks for in-memory fallback when Qdrant search is unavailable."""
    global _local_chunk_cache
    for i, chunk in enumerate(chunks):
        doc_id = ids[i] if i < len(ids) else str(i)
        meta = metadata_list[i] if i < len(metadata_list) else {}
        emb = embeddings[i] if embeddings and i < len(embeddings) else []
        existing = next((r for r in _local_chunk_cache if r["id"] == doc_id), None)
        row = {
            "id": doc_id,
            "document": chunk,
            "metadata": meta,
            "embedding": emb,
        }
        if existing:
            existing.update(row)
        else:
            _local_chunk_cache.append(row)


def _search_local_cache(
    query_vector: list[float],
    *,
    limit: int,
    metadata_filter: dict,
) -> list[dict[str, Any]]:
    if not _local_chunk_cache:
        return []

    query_vec = np.array(query_vector, dtype=float)
    query_norm = np.linalg.norm(query_vec)
    scored: list[dict[str, Any]] = []

    for item in _local_chunk_cache:
        meta = item.get("metadata") or {}
        if metadata_filter and not all(meta.get(k) == v for k, v in metadata_filter.items()):
            continue
        item_vec = np.array(item.get("embedding") or [], dtype=float)
        if item_vec.size == 0:
            item_vec = np.array(get_mock_embedding(item["document"]), dtype=float)
        item_norm = np.linalg.norm(item_vec)
        score = (
            float(np.dot(query_vec, item_vec) / (query_norm * item_norm))
            if query_norm > 0 and item_norm > 0
            else 0.0
        )
        scored.append(
            {
                "document": item["document"],
                "metadata": meta,
                "score": score,
                "id": item["id"],
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


class EmbeddingManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
            cls._instance.use_fallback = False
            cls._instance.use_remote = False
            cls._instance.use_qdrant_remote = False
            cls._instance.remote_base_url = ""
            cls._instance.remote_embed_path = "/embed"
            cls._instance.remote_query_path = "/query"
            cls._instance.remote_body_format = "text"
            cls._instance.remote_api_key = ""
            cls._instance.remote_timeout = 120
            cls._instance.initialized = False
        return cls._instance

    def _settings(self):
        return get_settings()

    def _remote_configured(self) -> bool:
        return bool(self._settings().embedding_service_url.strip())

    def _probe_health_mode(self, base_url: str, api_key: str, timeout: int) -> str | None:
        """Use GET /health when POST /embed is unreachable (e.g. ngrok offline)."""
        url = _service_url(base_url, "/health")
        headers = _request_headers(base_url, api_key)
        try:
            response = requests.get(url, headers=headers, timeout=min(timeout, 15))
        except requests.RequestException as exc:
            logger.debug("Embedding health probe failed: %s", exc)
            return None
        if response.status_code >= 400:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        service = str(payload.get("service", "")).lower()
        if "qdrant" in service or payload.get("qdrant_connected"):
            logger.info("Auto-detected embedding service mode=qdrant via /health at %s", base_url)
            return "qdrant"
        if payload.get("status") in ("ok", "starting"):
            logger.info("Auto-detected embedding service mode=vectors via /health at %s", base_url)
            return "vectors"
        return None

    def _detect_remote_mode(
        self,
        base_url: str,
        embed_path: str,
        api_key: str,
        timeout: int,
        body_format: str,
    ) -> str:
        """Probe remote /embed: vectors if response includes embedding, else qdrant."""
        try:
            payload = _post_json(
                url=_service_url(base_url, embed_path),
                headers=_request_headers(base_url, api_key),
                body={"text": "mode probe", "metadata": {}},
                timeout=min(timeout, 30),
            )
            if isinstance(payload, dict) and (
                "embedding" in payload or "embeddings" in payload or "vector" in payload
            ):
                logger.info(
                    "Auto-detected embedding service mode=vectors at %s%s",
                    base_url,
                    embed_path,
                )
                return "vectors"
            if _is_qdrant_upsert_response(payload):
                logger.info(
                    "Auto-detected embedding service mode=qdrant at %s%s",
                    base_url,
                    embed_path,
                )
                return "qdrant"
        except Exception as exc:
            logger.warning("Could not probe remote embedding service: %s", exc)

        health_mode = self._probe_health_mode(base_url, api_key, timeout)
        if health_mode:
            return health_mode

        settings = self._settings()
        if settings.qdrant_url.strip():
            logger.info(
                "Defaulting embedding service mode to qdrant (QDRANT_URL is set; "
                "verify EMBEDDING_SERVICE_URL reaches your embedding host)."
            )
            return "qdrant"

        logger.info("Defaulting embedding service mode to vectors.")
        return "vectors"

    def initialize(self):
        if self.initialized:
            return

        settings = self._settings()
        mode = (settings.embedding_service_mode or "auto").strip().lower()

        if settings.use_mock_embeddings and not self._remote_configured():
            logger.info("USE_MOCK_EMBEDDINGS is active. Using deterministic mock embeddings.")
            self.use_fallback = True
            self.use_remote = False
            self.use_qdrant_remote = False
            self.initialized = True
            return

        if self._remote_configured():
            self.use_remote = True
            self.use_fallback = False
            self.remote_base_url = _normalize_service_url(settings.embedding_service_url)
            resolved_mode = mode
            if mode == "auto":
                resolved_mode = self._detect_remote_mode(
                    self.remote_base_url,
                    _normalize_embed_path(settings.embedding_service_path),
                    settings.embedding_service_api_key,
                    settings.embedding_service_timeout,
                    settings.embedding_body_format,
                )
            self.use_qdrant_remote = resolved_mode in ("qdrant", "qdrant_store", "store")
            self.remote_embed_path = _normalize_embed_path(
                settings.embedding_service_path
            )
            self.remote_query_path = _normalize_query_path(
                settings.embedding_query_path
            )
            self.remote_body_format = _resolve_body_format(
                settings.embedding_body_format,
                self.remote_embed_path,
            )
            self.remote_api_key = settings.embedding_service_api_key
            self.remote_timeout = settings.embedding_service_timeout
            if self.use_qdrant_remote:
                from backend.tools.qdrant_tool import qdrant_client

                qdrant_client.initialize()
                logger.info(
                    "Embeddings via %s%s; vector search via Qdrant Cloud (query=%s).",
                    self.remote_base_url,
                    self.remote_embed_path,
                    self.remote_query_path,
                )
            else:
                logger.info(
                    "Using remote embedding service at %s%s (%s body).",
                    self.remote_base_url,
                    self.remote_embed_path,
                    self.remote_body_format,
                )
            self.initialized = True
            return

        logger.error(
            "No embedding backend configured. Set EMBEDDING_SERVICE_URL for production "
            "or USE_MOCK_EMBEDDINGS=true for local development."
        )
        self.use_fallback = True
        self.initialized = True

    def uses_local_model(self) -> bool:
        return not self.use_remote and not self.use_fallback

    def uses_qdrant_remote(self) -> bool:
        if not self.initialized:
            self.initialize()
        return self.use_qdrant_remote

    def get_embedding(self, text: str) -> list:
        batch = self.get_embeddings([text])
        return batch[0] if batch else []

    def get_embeddings(self, texts: list) -> list:
        if not self.initialized:
            self.initialize()

        if not texts:
            return []

        if self.use_qdrant_remote:
            raise RuntimeError(
                "get_embeddings is not available in qdrant mode; use upsert_chunks / search_chunks."
            )

        if self.use_remote:
            try:
                vectors = _fetch_remote_embeddings(
                    texts,
                    base_url=self.remote_base_url,
                    embed_path=self.remote_embed_path,
                    body_format=self.remote_body_format,
                    api_key=self.remote_api_key,
                    timeout=self.remote_timeout,
                    metadata_list=[{} for _ in texts],
                )
                logger.debug(
                    "Fetched %s embedding(s) from %s%s",
                    len(vectors),
                    self.remote_base_url,
                    self.remote_embed_path,
                )
                return vectors
            except Exception as e:
                logger.error(
                    "Remote embedding request failed (%s%s): %s",
                    self.remote_base_url,
                    self.remote_embed_path,
                    e,
                )
                raise

        if self.use_fallback:
            return [get_mock_embedding(t) for t in texts]

        return [get_mock_embedding(t) for t in texts]

    def upsert_chunks(
        self,
        chunks: list[str],
        metadata_list: list[dict],
        ids: list[str],
    ) -> list[str]:
        """Store chunks via remote /embed (Qdrant). Returns Qdrant point ids."""
        if not self.initialized:
            self.initialize()

        if not chunks:
            return []

        if self.use_qdrant_remote:
            point_ids: list[str] = []
            vectors: list[list[float]] = []
            for chunk, meta, chunk_id in zip(chunks, metadata_list, ids):
                payload_meta = {**meta, "chunk_id": chunk_id}
                url = _service_url(self.remote_base_url, self.remote_embed_path)
                headers = _request_headers(self.remote_base_url, self.remote_api_key)
                payload = _post_json(
                    url=url,
                    headers=headers,
                    body={"text": chunk, "metadata": payload_meta},
                    timeout=self.remote_timeout,
                )
                if _is_qdrant_upsert_response(payload):
                    point_ids.append(str(payload["id"]))
                else:
                    point_ids.append(chunk_id)
                try:
                    vectors.append(
                        _vectors_from_payload(payload, expected_count=1)[0]
                    )
                except RuntimeError:
                    vectors.append(get_mock_embedding(chunk))
            register_local_chunks(chunks, metadata_list, ids, vectors)
            return point_ids

        if self.use_fallback:
            return ids

        raise RuntimeError("upsert_chunks requires EMBEDDING_SERVICE_MODE=qdrant")

    def search_chunks(
        self,
        query_text: str,
        *,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Embed query via POST /query, then search Qdrant Cloud from this backend."""
        if not self.initialized:
            self.initialize()

        if self.use_qdrant_remote:
            from backend.tools.qdrant_tool import qdrant_client

            flat_where = where or {}
            try:
                query_vector = _fetch_query(
                    query_text,
                    base_url=self.remote_base_url,
                    query_path=self.remote_query_path,
                    api_key=self.remote_api_key,
                    timeout=self.remote_timeout,
                )
                return qdrant_client.search(
                    query_vector,
                    limit=n_results,
                    metadata_filter=flat_where,
                )
            except Exception as exc:
                logger.warning(
                    "Qdrant direct search failed (%s); falling back to local cache.",
                    exc,
                )
                return _search_local_cache(
                    get_mock_embedding(query_text),
                    limit=n_results,
                    metadata_filter=flat_where,
                )

        raise RuntimeError("search_chunks requires EMBEDDING_SERVICE_MODE=qdrant")


# Singleton helper
embedding_manager = EmbeddingManager()
