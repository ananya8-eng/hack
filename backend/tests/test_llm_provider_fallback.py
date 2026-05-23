"""LLM provider-chain fallback for JSON generation."""
from unittest.mock import patch

from backend.agents.llm_client import LLMClient


def test_generate_json_falls_back_to_second_provider_on_bad_json():
    client = LLMClient()
    responses = {
        "nvidia": "not json at all",
        "grok": '{"comparative_analysis": "peer tone is more cautious"}',
    }

    def fake_invoke(provider_name: str, prompt: str, temperature: float, timeout: int) -> str:
        return responses.get(provider_name, "")

    with patch.object(client, "_invoke_provider", side_effect=fake_invoke):
        parsed = client.generate_json(
            "Return comparative JSON",
            max_attempts=1,
            validator=lambda p: isinstance(p.get("comparative_analysis"), str),
        )

    assert parsed is not None
    assert "cautious" in parsed["comparative_analysis"]


def test_generate_json_skips_ollama_not_in_chain():
    client = LLMClient()
    chain_names = [name for name, _ in client._provider_chain("hi", 0.1, 30)]
    assert "ollama" not in chain_names
    assert chain_names == ["nvidia", "grok", "huggingface", "gemini"]
