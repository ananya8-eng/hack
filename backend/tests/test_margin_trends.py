from backend.extraction.margin_trends import (
    extract_fiscal_year,
    extract_gross_margin_percent,
    year_from_accession_dir,
    compute_margin_trends,
)


def test_year_from_accession_dir():
    assert year_from_accession_dir("0000320193-24-000123") == "2024"
    assert year_from_accession_dir("0000002488-23-000012") == "2023"


def test_extract_gross_margin_percent():
    text = "Gross margin expanded to 47% reflecting enterprise demand."
    assert extract_gross_margin_percent(text) == 47.0

    text2 = "Our gross margins were 74.0% for the fiscal year."
    assert extract_gross_margin_percent(text2) == 74.0


def test_extract_fiscal_year():
    text = "For the fiscal year ended January 28, 2024, revenue increased."
    assert extract_fiscal_year(text) == "2024"


def test_compute_margin_trends_with_mock_fetch():
    def fake_fetch(company: str, filing_type: str = "10-K", limit: int = 4):
        return [
            {
                "text": "For the fiscal year ended 2022. Gross margin was 54%.",
                "year": "2022",
            },
            {
                "text": "For the fiscal year ended 2023. Gross margin reached 61.5%.",
                "year": "2023",
            },
        ]

    out = compute_margin_trends(
        "NVIDIA",
        peer_company="AMD",
        fetch_filings_fn=fake_fetch,
    )
    assert out["target_label"] == "NVIDIA"
    assert len(out["points"]) >= 2
    years = {p["year"] for p in out["points"]}
    assert "2022" in years or "2023" in years
