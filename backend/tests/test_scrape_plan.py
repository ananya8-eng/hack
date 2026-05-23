from backend.tools.scrape_plan import (
    build_heuristic_scrape_requests,
    companies_from_requests,
    normalize_scraping_decision,
    targets_to_requests,
)


def test_heuristic_uses_user_query_as_web_search():
    result = build_heuristic_scrape_requests(
        "We face competition in our markets.",
        "What is Google's top 5 competitors?",
        "Google",
    )
    assert result["needs_scraping"] is True
    assert result["scrape_requests"][0]["type"] == "web_search"
    assert "Google's top 5 competitors" in result["scrape_requests"][0]["query"]


def test_normalize_llm_scrape_requests():
    payload = {
        "needs_scraping": True,
        "reason": "Peer context",
        "scrape_requests": [
            {
                "type": "web_search",
                "query": "Salesforce CRM market competitors 2025",
                "company": "CRM",
                "purpose": "Identify SaaS peers",
            },
            {
                "type": "sec_filing",
                "company": "ORCL",
                "filing_type": "10-K",
                "purpose": "Oracle filing comparison",
            },
        ],
    }
    out = normalize_scraping_decision(payload, "", "", "Salesforce")
    assert len(out["scrape_requests"]) == 2
    assert out["scrape_requests"][0]["type"] == "web_search"


def test_legacy_targets_converted():
    payload = {
        "needs_scraping": True,
        "reason": "Peers",
        "targets": ["META", "GOOGL_PRIOR"],
    }
    out = normalize_scraping_decision(payload, "competition risk", "compare peers", "Apple")
    types = {r["type"] for r in out["scrape_requests"]}
    assert "sec_filing" in types
    assert "prior_filing" in types


def test_companies_from_requests_includes_target():
    reqs = targets_to_requests(["META"], "Apple")
    names = companies_from_requests(reqs, "Apple")
    assert "APPLE" in names
    assert "META" in names
