from backend.tools.scrape_plan import (
    build_heuristic_scrape_requests,
    companies_from_requests,
    extract_peer_companies,
    is_comparison_query,
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


def test_is_comparison_query_detects_peer_language():
    assert is_comparison_query("Compare NVIDIA against AMD on supply chain", "")
    assert not is_comparison_query("What are the top three risks?", "")


def test_extract_peer_companies_from_natural_language():
    peers = extract_peer_companies(
        "Compare NVIDIA against AMD on gross margins and supply chain risks",
        "NVIDIA",
    )
    assert "Amd" in peers or "AMD" in [p.upper() for p in peers]


def test_heuristic_requires_explicit_query():
    result = build_heuristic_scrape_requests(
        "Competition in our markets.",
        "",
        "Acme Corp",
    )
    assert result["needs_scraping"] is False


def test_heuristic_adds_sec_filing_for_named_peer():
    result = build_heuristic_scrape_requests(
        "Competition in accelerators.",
        "Compare NVIDIA against Intel on data center growth",
        "NVIDIA",
    )
    types = {r["type"] for r in result["scrape_requests"]}
    assert "web_search" in types
    assert "sec_filing" in types
    companies = {str(r.get("company", "")).upper() for r in result["scrape_requests"]}
    assert any("INTEL" in c for c in companies)
