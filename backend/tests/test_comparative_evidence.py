from backend.agents.analysis_heuristics import comparative_analysis_from_contexts


def test_comparative_fallback_uses_only_retrieved_text():
    original = {
        "executive_summary": "Revenue grew on cloud demand.",
        "risks": [
            {
                "risk_name": "Supply chain",
                "evidence": "We depend on single-source manufacturing partners.",
            }
        ],
    }
    scraped = [
        {
            "company": "PeerCo",
            "source": "SEC 10-K",
            "text": "PeerCo faces competition and supply uncertainty in key markets.",
        }
    ]
    out = comparative_analysis_from_contexts(
        original,
        scraped,
        "Acme",
        user_query="Compare Acme against PeerCo on supply chain risk",
    )
    assert "PeerCo" in out["comparative_analysis"]
    assert "AMD" not in out["comparative_analysis"]
    assert "74%" not in out["comparative_analysis"]
    assert len(out["competitor_benchmarks"]) >= 1
    assert out["competitor_benchmarks"][0]["competitor_company"] == "PeerCo"
