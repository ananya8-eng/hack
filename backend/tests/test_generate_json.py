from unittest.mock import MagicMock, patch

from backend.agents import llm_client as llm_module
from backend.guardrails.types import GuardrailResult


@patch.object(llm_module.guardrails, "check_llm_json_output", side_effect=lambda p: GuardrailResult.ok(metadata={"json": p}))
@patch.object(llm_module.guardrails, "prepare_llm_prompt", side_effect=lambda p: GuardrailResult.ok(p))
def test_generate_json_retries_until_valid(_prep, _json_guard, monkeypatch):
    client = llm_module.LLMClient()
    responses = [
        "Here is the analysis without JSON",
        '{"risks": [], "sentiment": {"score": 0.1}}',
    ]
    invoke_mock = MagicMock(side_effect=responses)
    monkeypatch.setattr(client, "_invoke_provider", invoke_mock)

    parsed = client.generate_json('Return {"risks": []}', max_attempts=3)
    assert parsed is not None
    assert parsed["sentiment"]["score"] == 0.1
    assert invoke_mock.call_count == 2


@patch.object(llm_module.guardrails, "check_llm_json_output", side_effect=lambda p: GuardrailResult.ok(metadata={"json": p}))
@patch.object(llm_module.guardrails, "prepare_llm_prompt", side_effect=lambda p: GuardrailResult.ok(p))
def test_generate_json_returns_none_after_max_attempts(_prep, _json_guard, monkeypatch):
    client = llm_module.LLMClient()
    monkeypatch.setattr(client, "_invoke_provider", MagicMock(return_value="not json at all"))

    parsed = client.generate_json('Return {"ok": true}', max_attempts=2)
    assert parsed is None
