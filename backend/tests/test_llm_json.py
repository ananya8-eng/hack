from backend.agents.llm_client import parse_json_from_llm


def test_parse_json_from_markdown_fence():
    text = """Here is the analysis:
```json
{"risks": [], "sentiment": {"score": 0.2}, "needs_scraping": true}
```
"""
    parsed = parse_json_from_llm(text)
    assert parsed is not None
    assert parsed["needs_scraping"] is True


def test_parse_json_with_nested_braces_in_strings():
    text = (
        'Answer: {"risks": [{"evidence": "risk {macro}"}], '
        '"sentiment": {"score": -0.1}, "needs_scraping": false}'
    )
    parsed = parse_json_from_llm(text)
    assert parsed is not None
    assert parsed["needs_scraping"] is False
