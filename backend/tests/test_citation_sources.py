from backend.rag.citation_sources import (
    benchmark_supported_by_corpus,
    companies_match,
    sanitize_competitor_benchmarks,
)


def test_companies_match_apple_aapl():
    assert companies_match("Apple", "AAPL")
    assert companies_match("Apple Inc", "apple")
    assert companies_match("Microsoft", "MSFT")


def test_sanitize_drops_self_comparison():
    benchmarks = [
        {
            "metric_name": "Revenue",
            "target_company": "Apple",
            "competitor_company": "Apple",
            "comparison_value": "$100B vs $90B",
        },
        {
            "metric_name": "Risk density",
            "target_company": "Apple",
            "competitor_company": "Microsoft",
            "comparison_value": "Apple: more supply-chain mentions than Microsoft in excerpts",
        },
    ]
    corpus = "Apple faces supply chain risk. Microsoft competes in cloud services."
    cleaned = sanitize_competitor_benchmarks(benchmarks, "Apple", corpus)
    assert len(cleaned) == 1
    assert cleaned[0]["competitor_company"] == "Microsoft"


def test_sanitize_drops_unsupported_financial_numbers():
    benchmarks = [
        {
            "metric_name": "Revenue",
            "competitor_company": "Microsoft",
            "comparison_value": "$123.4 billion (Q1 2026) vs. $89.6 billion (Q1 2026)",
        }
    ]
    corpus = "We discuss competition and gross margin pressure in our industry."
    cleaned = sanitize_competitor_benchmarks(benchmarks, "Apple", corpus)
    assert cleaned == []


def test_benchmark_supported_when_number_in_corpus():
    assert benchmark_supported_by_corpus(
        "Gross margin was 38.4% in the period discussed.",
        "Our gross margin was 38.4% for the fiscal year.",
    )
