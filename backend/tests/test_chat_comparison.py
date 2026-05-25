from unittest.mock import MagicMock, patch

from backend.rag.chat_comparison import run_chat_peer_comparison


def test_non_comparison_query_not_handled():
    report = {"company_name": "NVIDIA", "result": {"sections": {"risk": "competition"}}}
    out = run_chat_peer_comparison(report, "What are NVIDIA's main competitors?")
    assert out.get("handled") is False
    out2 = run_chat_peer_comparison(report, "What is the biggest operational risk?")
    assert out2.get("handled") is False


@patch("backend.rag.chat_comparison.run_comparative_with_healing")
@patch("backend.rag.chat_comparison.run_scrape_with_healing")
@patch("backend.rag.chat_comparison.validator_agent")
@patch("backend.rag.chat_comparison.financial_scraper")
def test_comparison_flow_returns_slm_answer(
    mock_scraper, mock_validator, mock_scrape_heal, mock_comp_heal
):
    mock_scraper.resolve_ticker.side_effect = lambda c: c.upper()
    mock_scrape_heal.return_value = (
        [
            {
                "text": "AMD faces TSMC packaging constraints.",
                "source": "SEC 10-K",
                "company": "AMD",
                "filing_type": "10-K",
            }
        ],
        [],
        [],
    )
    mock_validator.validate_scraped_content.return_value = {
        "is_valid": True,
        "cleaned_content": "AMD faces TSMC packaging constraints.",
        "relevance_score": 0.9,
        "freshness_rating": "Recent",
    }
    mock_comp_heal.return_value = (
        {
            "comparative_analysis": "NVIDIA shows higher margin power than AMD.",
            "competitor_benchmarks": [
                {
                    "metric_name": "Gross margin",
                    "target_company": "NVIDIA",
                    "competitor_company": "AMD",
                    "comparison_value": "74% vs 47%",
                }
            ],
            "tone_shifts": [],
            "explainability_synthesis": "Margin gap reflects CUDA moat.",
        },
        [],
    )

    report = {
        "company_name": "NVIDIA",
        "result": {
            "sections": {"mda": "We compete with AMD in accelerators."},
            "risks": [{"risk_name": "Supply chain", "severity": "High"}],
            "sentiment": {"score": 0.4},
            "executive_summary": "Strong data center growth.",
        },
    }

    out = run_chat_peer_comparison(
        report, "Compare NVIDIA against AMD on gross margins"
    )
    assert out["handled"] is True
    assert out["mode"] == "comparison"
    assert out["success"] is True
    assert "AMD" in out["answer"]
    assert len(out["citations"]) >= 1
