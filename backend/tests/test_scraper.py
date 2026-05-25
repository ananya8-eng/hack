import os
import sys
from types import ModuleType
from unittest.mock import MagicMock, mock_open, patch

from backend.tools.scraper import FinancialScraper


def _sec_edgar_patch():
    """Stub sec_edgar_downloader so tests run without the optional package installed."""
    stub = ModuleType("sec_edgar_downloader")
    mock_cls = MagicMock()
    stub.Downloader = mock_cls
    return patch.dict(sys.modules, {"sec_edgar_downloader": stub}), mock_cls


@patch("backend.tools.scraper.requests.get")
def test_fetch_sec_filing_normal(mock_requests_get):
    scraper = FinancialScraper(download_dir="fake_download_dir")
    scraper.resolve_ticker = MagicMock(return_value="AAPL")

    sec_patch, mock_downloader_cls = _sec_edgar_patch()
    with sec_patch, \
         patch("os.path.isdir", return_value=True), \
         patch("os.listdir") as mock_listdir, \
         patch("os.walk") as mock_walk, \
         patch("builtins.open", mock_open(read_data="Normal filing content text" * 2000)):  # long enough to test 12000 cutoff

        mock_dl = MagicMock()
        mock_downloader_cls.return_value = mock_dl
        mock_dl.get.return_value = 1  # count > 0

        # Mock os.listdir to return folders (unsorted)
        mock_listdir.return_value = ["0000320193-24-000123", "0000320193-23-000106"]

        # Mock os.walk to find a text file in the newest folder
        mock_walk.return_value = [
            ("fake_download_dir/sec-edgar-filings/AAPL/10-K/0000320193-24-000123", [], ["filing.txt"])
        ]

        # Execute normal request
        result = scraper.fetch_sec_filing("Apple", "10-K")

        # Assertions
        scraper.resolve_ticker.assert_called_once_with("Apple")
        # Change 2: limit=2 always
        mock_dl.get.assert_called_once_with("10-K", "AAPL", limit=2)
        mock_listdir.assert_called_once_with(
            os.path.join("fake_download_dir", "sec-edgar-filings", "AAPL", "10-K")
        )
        # Should walk into the newest dir (ending with 24-000123)
        mock_walk.assert_called_once_with(
            os.path.join("fake_download_dir", "sec-edgar-filings", "AAPL", "10-K", "0000320193-24-000123")
        )
        assert result["success"] is True
        # Normal limits to 12000 chars
        assert len(result["text"]) <= 12000
        assert "Normal filing content text" in result["text"]
        assert result["company"] == "AAPL"
        assert result["filing_type"] == "10-K"


@patch("backend.tools.scraper.requests.get")
def test_fetch_sec_filing_prior_generic(mock_requests_get):
    """Verifies that any filing type (e.g. 10-Q) is stripped and works correctly for prior years."""
    scraper = FinancialScraper(download_dir="fake_download_dir")
    scraper.resolve_ticker = MagicMock(return_value="AAPL")

    sec_patch, mock_downloader_cls = _sec_edgar_patch()
    with sec_patch, \
         patch("os.path.isdir", return_value=True), \
         patch("os.listdir") as mock_listdir, \
         patch("os.walk") as mock_walk, \
         patch("builtins.open", mock_open(read_data="Prior year filing content text " * 3000)):  # very long string to test 50000 cutoff

        mock_dl = MagicMock()
        mock_downloader_cls.return_value = mock_dl
        mock_dl.get.return_value = 2  # count > 0

        # Mock os.listdir to return folders (unsorted)
        mock_listdir.return_value = ["0000320193-24-000123", "0000320193-23-000106"]

        # Mock os.walk to find a text file in the oldest folder
        mock_walk.return_value = [
            ("fake_download_dir/sec-edgar-filings/AAPL/10-Q/0000320193-23-000106", [], ["filing.txt"])
        ]

        # Execute with 10-Q-PRIOR
        result = scraper.fetch_sec_filing("Apple", "10-Q-PRIOR")

        # Assertions
        scraper.resolve_ticker.assert_called_once_with("Apple")
        # Stripped from 10-Q-PRIOR to 10-Q, and requested with limit=2
        mock_dl.get.assert_called_once_with("10-Q", "AAPL", limit=2)
        mock_listdir.assert_called_once_with(
            os.path.join("fake_download_dir", "sec-edgar-filings", "AAPL", "10-Q")
        )
        # Should walk into the oldest dir (ending with 23-000106)
        mock_walk.assert_called_once_with(
            os.path.join("fake_download_dir", "sec-edgar-filings", "AAPL", "10-Q", "0000320193-23-000106")
        )
        assert result["success"] is True
        # Prior year has larger truncation limit of 50000 chars (longer than 12000 chars)
        assert len(result["text"]) > 12000
        assert len(result["text"]) <= 50000
        assert "Prior year filing content text" in result["text"]
        assert result["company"] == "AAPL"
        assert result["filing_type"] == "10-Q-PRIOR"


@patch("backend.tools.scraper.requests.post")
def test_web_search_returns_lite_snippets(mock_post):
    html = """
    <html><body>
    <a class="result-link" href="https://example.com/competitors">Apple Competitors</a>
    <td class="result-snippet">Apple competes with Samsung and Google in smartphones worldwide.</td>
    </body></html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    scraper = FinancialScraper(download_dir="fake_download_dir")
    result = scraper.web_search("Apple smartphone competitors", company="Apple")

    assert result["success"] is True
    assert "Samsung" in result["text"]
    assert len(result["text"]) >= 100


def test_execute_scrape_request_prior_propagates_correctly():
    """Verify execute_scrape_request calls fetch_sec_filing with -PRIOR suffix."""
    scraper = FinancialScraper(download_dir="fake_download_dir")
    scraper.fetch_sec_filing = MagicMock(return_value={"success": True, "text": "Content", "company": "AAPL"})

    request = {
        "type": "prior_filing",
        "company": "AAPL",
        "filing_type": "10-Q",
        "query": ""
    }

    res = scraper.execute_scrape_request(request)

    # Should call with f"{filing_type}-PRIOR" (e.g. "10-Q-PRIOR")
    scraper.fetch_sec_filing.assert_called_once_with("AAPL", "10-Q-PRIOR")
    assert res["filing_type"] == "10-Q-PRIOR"
