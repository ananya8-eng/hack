import numpy as np

from backend.tools.chroma_tool import _flatten_embedding
from backend.tools.embedding_tool import EmbeddingManager, _as_flat_embedding


def test_as_flat_embedding_unwraps_single_batch_row():
    vector = np.random.randn(1, 8)
    flat = _as_flat_embedding(vector)
    assert flat
    assert isinstance(flat[0], float)
    assert not isinstance(flat[0], list)


def test_as_flat_embedding_keeps_already_flat():
    flat = _as_flat_embedding([0.1, 0.2, 0.3])
    assert flat == [0.1, 0.2, 0.3]


def test_get_embedding_is_flat_for_single_text(monkeypatch):
    manager = EmbeddingManager()
    manager.initialized = True
    manager.use_fallback = False

    fake_vectors = np.random.randn(1, 16)

    class FakeModel:
        def encode(self, texts, **kwargs):
            return fake_vectors

    manager.model = FakeModel()
    emb = manager.get_embedding("sample filing chunk")
    assert emb
    assert isinstance(emb[0], float)


def test_flatten_embedding_triple_nested():
    nested = [[[0.1, 0.2]]]
    assert _flatten_embedding(nested) == [0.1, 0.2]
