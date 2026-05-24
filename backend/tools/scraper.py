import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from backend.config import get_settings

logger = logging.getLogger(__name__)

_SEC_TICKERS_CACHE: Optional[Dict[str, str]] = None
_VALID_TICKERS: Optional[set[str]] = None

# Common brand/name → SEC ticker (LLM often outputs these incorrectly)
_TICKER_ALIASES: Dict[str, str] = {
    "APPLE": "AAPL",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "FACEBOOK": "META",
    "AMAZON": "AMZN",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "TESLA": "TSLA",
    "NETFLIX": "NFLX",
}


class FinancialScraper:
    def __init__(self, download_dir: str | None = None):
        settings = get_settings()
        self.download_dir = download_dir or settings.scraped_filings_dir
        self._user_agent = settings.scraper_user_agent
        self._sec_company = settings.sec_edgar_company_name
        self._sec_email = settings.sec_edgar_email
        os.makedirs(self.download_dir, exist_ok=True)

    def scrape_url(self, url: str) -> str:
        """Scrapes a webpage using BeautifulSoup and returns clean text."""
        try:
            headers = {"User-Agent": self._user_agent}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                lines = (line.strip() for line in soup.get_text().splitlines())
                return "\n".join(line for line in lines if line)
        except Exception as e:
            logger.debug("URL scrape failed %s: %s", url, e)
        return ""

    def _load_sec_tickers(self) -> None:
        global _SEC_TICKERS_CACHE, _VALID_TICKERS
        if _SEC_TICKERS_CACHE is not None:
            return
        _SEC_TICKERS_CACHE = {}
        _VALID_TICKERS = set()
        try:
            resp = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": f"{self._sec_company} {self._sec_email}"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for entry in data.values():
                title = str(entry.get("title", "")).strip()
                ticker = str(entry.get("ticker", "")).strip().upper()
                if title and ticker:
                    _SEC_TICKERS_CACHE[title.upper()] = ticker
                    _SEC_TICKERS_CACHE[ticker] = ticker
                    _VALID_TICKERS.add(ticker)
        except Exception as e:
            logger.warning("SEC ticker lookup unavailable: %s", e)

    def resolve_ticker(self, company: str) -> str:
        """Resolve a company name or ticker via SEC company_tickers.json."""
        raw = company.strip()
        if not raw:
            return ""

        self._load_sec_tickers()
        key = raw.upper().replace(",", "").strip()

        if key in _TICKER_ALIASES:
            return _TICKER_ALIASES[key]

        first_token = key.split()[0] if key.split() else ""
        if first_token in _TICKER_ALIASES:
            return _TICKER_ALIASES[first_token]

        if _VALID_TICKERS and key in _VALID_TICKERS:
            return key

        if _SEC_TICKERS_CACHE and key in _SEC_TICKERS_CACHE:
            return _SEC_TICKERS_CACHE[key]

        if _SEC_TICKERS_CACHE:
            for title, ticker in _SEC_TICKERS_CACHE.items():
                if title == key:
                    continue
                if re.search(rf"\b{re.escape(key)}\b", title):
                    return ticker
                if key in title:
                    return ticker

        if re.fullmatch(r"[A-Z]{1,5}", key):
            logger.warning(
                "Could not resolve '%s' to a known SEC ticker; download may fail",
                company,
            )
            return key

        return key.upper().replace(" ", "_")[:8]

    def _duckduckgo_result_urls(self, query: str, max_results: int = 3) -> List[str]:
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {"User-Agent": self._user_agent}
        try:
            response = requests.post(search_url, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as e:
            logger.warning("Web search request failed: %s", e)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        urls: List[str] = []
        for link in soup.select("a.result__a"):
            href = link.get("href", "")
            if not href:
                continue
            if "uddg=" in href:
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                uddg = qs.get("uddg", [""])[0]
                href = unquote(uddg) if uddg else href
            if href.startswith("http") and href not in urls:
                urls.append(href)
            if len(urls) >= max_results:
                break
        return urls

    def web_search(self, query: str, company: str = "", max_results: int = 3) -> dict:
        """
        Run a natural-language web search, scrape top result pages, and return combined text.
        Example query: "what is google's top 5 competitors?"
        """
        logger.info("Web search: %s", query[:120])
        urls = self._duckduckgo_result_urls(query, max_results=max_results)
        if not urls:
            return {
                "success": False,
                "source": f"Web Search (no results): {query[:80]}",
                "text": "",
                "company": (company or "EXTERNAL").upper(),
                "filing_type": "WEB",
                "search_query": query,
            }

        parts: List[str] = []
        used_urls: List[str] = []
        for url in urls:
            page_text = self.scrape_url(url)
            if len(page_text.strip()) < 200:
                continue
            parts.append(f"--- Source: {url} ---\n{page_text[:6000]}")
            used_urls.append(url)

        combined = "\n\n".join(parts)
        label = (company or "EXTERNAL").upper().strip() or "EXTERNAL"
        return {
            "success": bool(combined.strip()),
            "source": f"Web Search ({query[:60]})",
            "text": combined[:18000],
            "company": label,
            "filing_type": "WEB",
            "search_query": query,
            "urls": used_urls,
        }

    def fetch_sec_filing(self, company: str, filing_type: str = "10-K") -> dict:
        """Fetch a filing from SEC EDGAR for any resolvable company/ticker."""
        ticker = self.resolve_ticker(company)
        
        # Check if filing_type ends with -PRIOR
        is_prior = filing_type.upper().endswith("-PRIOR")
        actual_type = filing_type[:-6] if is_prior else filing_type
        actual_upper = actual_type.upper().strip() or "10-K"
        filing_upper = filing_type.upper().strip() or "10-K"

        logger.info("Fetching %s filing for: %s (%s)", filing_upper, company, ticker)

        try:
            from sec_edgar_downloader import Downloader

            dl = Downloader(
                self._sec_company,
                self._sec_email,
                self.download_dir,
            )
            count = dl.get(actual_type, ticker, limit=2)
            if count > 0:
                base = os.path.join(
                    self.download_dir, "sec-edgar-filings", ticker, actual_upper
                )
                if os.path.isdir(base):
                    subdirs = [
                        os.path.join(base, d)
                        for d in os.listdir(base)
                        if os.path.isdir(os.path.join(base, d))
                    ]
                    if subdirs:
                        subdirs.sort()
                        selected_dir = subdirs[0] if is_prior else subdirs[-1]
                        for root, _, files in os.walk(selected_dir):
                            for fname in files:
                                if fname.endswith((".txt", ".html")):
                                    path = os.path.join(root, fname)
                                    with open(
                                        path, "r", encoding="utf-8", errors="ignore"
                                    ) as fh:
                                        raw = fh.read()
                                    if fname.endswith(".html"):
                                        text = BeautifulSoup(raw, "html.parser").get_text()
                                    else:
                                        text = raw
                                    text = " ".join(text.split())[:50000 if is_prior else 12000]
                                    logger.info(
                                        "SEC Edgar filing retrieved for %s (%s chars)",
                                        ticker,
                                        len(text),
                                    )
                                    return {
                                        "success": True,
                                        "source": f"SEC EDGAR Live ({ticker} {filing_upper})",
                                        "text": text,
                                        "company": ticker,
                                        "filing_type": filing_upper,
                                    }
        except Exception as e:
            logger.warning("SEC Edgar download failed for %s: %s", ticker, e)
            return {
                "success": False,
                "source": f"SEC EDGAR ({ticker} {filing_upper})",
                "text": "",
                "company": ticker,
                "filing_type": filing_upper,
                "error": str(e),
                "resolved_ticker": ticker,
                "input_company": company,
            }

        return {
            "success": False,
            "source": f"SEC EDGAR ({ticker} {filing_upper})",
            "text": "",
            "company": ticker,
            "filing_type": filing_upper,
            "error": "No filing files found after download",
            "resolved_ticker": ticker,
            "input_company": company,
        }

    def execute_scrape_request(self, request: Dict[str, Any]) -> dict:
        """Run one LLM-planned scrape request (web search, SEC filing, or prior filing)."""
        req_type = str(request.get("type") or "web_search").lower()
        company = str(request.get("company") or "").strip()
        query = str(request.get("query") or "").strip()
        filing_type = str(request.get("filing_type") or "10-K").strip()

        if req_type == "web_search":
            return self.web_search(query, company=company)

        if req_type == "prior_filing":
            res = self.fetch_sec_filing(company, f"{filing_type}-PRIOR")
            if res.get("success"):
                res = {
                    **res,
                    "company": company.upper(),
                    "source": f"Prior Period SEC Context ({res.get('company')} {filing_type})",
                    "filing_type": f"{filing_type}-PRIOR",
                }
            return res

        return self.fetch_sec_filing(company, filing_type)


financial_scraper = FinancialScraper()
