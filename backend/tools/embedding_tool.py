import hashlib
import logging
from urllib.parse import urljoin

import numpy as np
import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)

_EMBED_PATH = "/v1/embeddings"


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


def get_mock_embedding(text: str, dim: int = 1024) -> list:
    """
    Generates deterministic, normalized 1024-dimensional mock embeddings
    using a SHA-256 hash seed. Extremely fast and requires no downloads,
    ideal as a fallback for local dev/tests.
    """
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


def _fetch_remote_embeddings(
    texts: list[str],
    *,
    base_url: str,
    api_key: str,
    timeout: int,
) -> list[list[float]]:
    url = urljoin(_normalize_service_url(base_url) + "/", _EMBED_PATH.lstrip("/"))
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    response = requests.post(
        url,
        json={"texts": texts},
        headers=headers,
        timeout=timeout,
    )
    if response.status_code >= 400:
        detail = response.text[:500]
        raise RuntimeError(
            f"Embedding service returned {response.status_code}: {detail}"
        )

    payload = response.json()
    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise RuntimeError(
            f"Embedding service returned invalid payload (expected {len(texts)} vectors)"
        )
    return [_as_flat_embedding(row) for row in embeddings]


class EmbeddingManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
            cls._instance.use_fallback = False
            cls._instance.use_remote = False
            cls._instance.remote_base_url = ""
            cls._instance.remote_api_key = ""
            cls._instance.remote_timeout = 120
            cls._instance.initialized = False
        return cls._instance

    def _settings(self):
        return get_settings()

    def _remote_configured(self) -> bool:
        return bool(self._settings().embedding_service_url.strip())

    def initialize(self):
        if self.initialized:
            return

        settings = self._settings()
        if settings.use_mock_embeddings and not self._remote_configured():
            logger.info("USE_MOCK_EMBEDDINGS is active. Using deterministic mock embeddings.")
            self.use_fallback = True
            self.use_remote = False
            self.initialized = True
            return

        if self._remote_configured():
            self.use_remote = True
            self.use_fallback = False
            self.remote_base_url = _normalize_service_url(settings.embedding_service_url)
            self.remote_api_key = settings.embedding_service_api_key
            self.remote_timeout = settings.embedding_service_timeout
            logger.info(
                "Using remote embedding service at %s (no local model).",
                self.remote_base_url,
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

    def get_embedding(self, text: str) -> list:
        batch = self.get_embeddings([text])
        return batch[0] if batch else []

    def get_embeddings(self, texts: list) -> list:
        if not self.initialized:
            self.initialize()

        if not texts:
            return []

        if self.use_remote:
            try:
                return _fetch_remote_embeddings(
                    texts,
                    base_url=self.remote_base_url,
                    api_key=self.remote_api_key,
                    timeout=self.remote_timeout,
                )
            except Exception as e:
                logger.error("Remote embedding request failed: %s", e)
                raise

        if self.use_fallback:
            return [get_mock_embedding(t) for t in texts]

        return [get_mock_embedding(t) for t in texts]


# Singleton helper
embedding_manager = EmbeddingManager()
