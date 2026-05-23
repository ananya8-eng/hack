from unittest.mock import MagicMock

from backend.agents import llm_client as llm_module


def test_generate_json_retries_until_valid(monkeypatch):
    client = llm_module.LLMClient()
    responses = [
        "Here is the analysis without JSON",
        '{"risks": [], "sentiment": {"score": 0.1}}',
    ]
    generate_mock = MagicMock(side_effect=responses)
    monkeypatch.setattr(client, "generate", generate_mock)

    parsed = client.generate_json('Return {"risks": []}', max_attempts=3)
    assert parsed is not None
    assert parsed["sentiment"]["score"] == 0.1
    assert generate_mock.call_count == 2


def test_generate_json_returns_none_after_max_attempts(monkeypatch):
    client = llm_module.LLMClient()
    monkeypatch.setattr(client, "generate", MagicMock(return_value="not json at all"))

    parsed = client.generate_json('Return {"ok": true}', max_attempts=2)
    assert parsed is None
