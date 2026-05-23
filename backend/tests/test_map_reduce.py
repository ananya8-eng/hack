"""Map-reduce merge logic tests."""
from backend.agents.map_reduce_analysis import _merge_risks, _average_sentiment


def test_merge_risks_dedupes_by_name():
    partials = [
        {"risks": [{"risk_name": "Supply Chain", "severity": "High"}]},
        {"risks": [{"risk_name": "supply chain", "severity": "Medium"}]},
        {"risks": [{"risk_name": "Regulatory", "severity": "Low"}]},
    ]
    merged = _merge_risks(partials)
    assert len(merged) == 2


def test_average_sentiment_combines_partials():
    partials = [
        {"sentiment_signals": {"score": 0.2, "optimism": 0.5, "pessimism": 0.1, "cautiousness": 0.2, "uncertainty": 0.1}},
        {"sentiment_signals": {"score": -0.1, "optimism": 0.3, "pessimism": 0.3, "cautiousness": 0.3, "uncertainty": 0.2}},
    ]
    sent = _average_sentiment(partials)
    assert "score" in sent
    assert sent["classification"] in ("Positive", "Negative", "Neutral")
