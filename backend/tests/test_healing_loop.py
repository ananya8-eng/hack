from unittest.mock import MagicMock, patch

from backend.agents.healing_loop import (
    run_scrape_with_healing,
    validate_analysis_for_healing,
)
from backend.tools.scraper import FinancialScraper


def test_validate_analysis_flags_apple_ticker():
    analysis = {
        "risks": [{"risk_name": "x"}],
        "sentiment": {"score": 0.1},
        "executive_summary": "ok",
        "needs_scraping": True,
        "scrape_requests": [
            {"type": "sec_filing", "company": "APPLE", "filing_type": "10-K"}
        ],
    }
    issues = validate_analysis_for_healing(analysis)
    assert any("AAPL" in issue for issue in issues)


def test_resolve_ticker_apple_alias():
    scraper = FinancialScraper()
    with patch.object(scraper, "_load_sec_tickers"):
        assert scraper.resolve_ticker("APPLE") == "AAPL"
        assert scraper.resolve_ticker("Apple Inc") == "AAPL"


def test_run_scrape_with_healing_retries_on_failure(monkeypatch):
    calls = {"n": 0}

    def fake_execute(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "success": False,
                "error": "Ticker 'APPLE' is invalid",
                "company": "APPLE",
            }
        return {"success": True, "text": "filing text", "source": "SEC", "company": "AAPL"}

    revised = [
        {
            "type": "sec_filing",
            "company": "AAPL",
            "filing_type": "10-K",
            "query": "",
            "purpose": "fixed ticker",
        }
    ]

    with patch(
        "backend.agents.healing_loop.revise_scrape_requests",
        return_value=revised,
    ):
        results, failures, logs = run_scrape_with_healing(
            [{"type": "sec_filing", "company": "APPLE", "filing_type": "10-K", "query": ""}],
            execute_fn=fake_execute,
            company_name="Apple",
            user_query="competitors",
        )

    assert len(results) == 1
    assert results[0]["success"] is True
    assert any("revision" in log.lower() or "retry" in log.lower() for log in logs)


def test_run_scrape_healing_stops_without_revised_plan(monkeypatch):
    with patch("backend.agents.healing_loop.revise_scrape_requests", return_value=[]):
        results, failures, _ = run_scrape_with_healing(
            [{"type": "sec_filing", "company": "APPLE", "filing_type": "10-K", "query": ""}],
            execute_fn=MagicMock(
                return_value={"success": False, "error": "bad ticker"}
            ),
            company_name="Apple",
            user_query="",
        )
    assert not results
    assert failures
