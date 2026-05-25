import numpy as np

from backend.tools.chroma_tool import (
    _chroma_where_strategies,
    _flatten_embedding,
    _flatten_where_for_memory,
    _metadata_matches_where,
    _normalize_where_for_chroma,
)
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


def test_get_embedding_mock_fallback_is_flat(monkeypatch):
    manager = EmbeddingManager()
    manager.initialized = True
    manager.use_fallback = True
    manager.use_remote = False
    emb = manager.get_embedding("sample filing chunk")
    assert emb
    assert isinstance(emb[0], float)
    assert len(emb) == 1024


def test_flatten_embedding_triple_nested():
    nested = [[[0.1, 0.2]]]
    assert _flatten_embedding(nested) == [0.1, 0.2]


def test_normalize_where_wraps_multi_key_filters():
    where = {"company": "Apple", "section": "mda"}
    assert _normalize_where_for_chroma(where) == {
        "$and": [{"company": "Apple"}, {"section": "mda"}],
    }


def test_flatten_where_for_memory_from_and_clause():
    where = {"$and": [{"company": "Apple"}, {"section": "mda"}]}
    assert _flatten_where_for_memory(where) == {"company": "Apple", "section": "mda"}


def test_metadata_matches_where():
    meta = {"company": "Apple", "section": "mda"}
    assert _metadata_matches_where(meta, {"company": "Apple"})
    assert not _metadata_matches_where(meta, {"company": "AMD"})


def test_chroma_where_strategies_company_only_uses_post_filter():
    strategies = _chroma_where_strategies({"company": "Apple"})
    assert strategies == [(None, {"company": "Apple"})]


def test_chroma_where_strategies_company_and_section_has_fallbacks():
    strategies = _chroma_where_strategies({"company": "Apple", "section": "mda"})
    assert strategies[0][0] == {"$and": [{"company": "Apple"}, {"section": "mda"}]}
    assert strategies[-1] == (None, {"company": "Apple", "section": "mda"})
