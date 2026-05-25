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

    def _duckduckgo_lite_results(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        DuckDuckGo Lite returns parseable snippets + links (more reliable than html.duckduckgo.com).
        """
        headers = {"User-Agent": self._user_agent}
        try:
            response = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": query},
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning("DuckDuckGo Lite search failed: %s", e)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        snippets = [
            td.get_text(" ", strip=True)
            for td in soup.select("td.result-snippet")
            if td.get_text(strip=True)
        ]
        links = []
        for anchor in soup.select("a.result-link"):
            href = str(anchor.get("href") or "").strip()
            title = anchor.get_text(" ", strip=True)
            if href.startswith("http"):
                links.append({"url": href, "title": title})

        results: List[Dict[str, str]] = []
        for i in range(max(len(snippets), len(links))):
            if i >= max_results:
                break
            entry: Dict[str, str] = {}
            if i < len(links):
                entry["url"] = links[i]["url"]
                entry["title"] = links[i].get("title") or ""
            if i < len(snippets):
                entry["snippet"] = snippets[i]
            if entry:
                results.append(entry)
        return results

    def _duckduckgo_result_urls(self, query: str, max_results: int = 3) -> List[str]:
        lite = self._duckduckgo_lite_results(query, max_results=max_results)
        urls = [r["url"] for r in lite if r.get("url")]
        if urls:
            return urls

        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {"User-Agent": self._user_agent}
        try:
            response = requests.post(search_url, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as e:
            logger.warning("Web search request failed: %s", e)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        urls = []
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

    def web_search(self, query: str, company: str = "", max_results: int = 5) -> dict:
        """
        Web search via DuckDuckGo Lite snippets (+ optional page scrape).
        Returns combined snippet text even when target sites block scraping.
        """
        logger.info("Web search: %s", query[:120])
        lite_results = self._duckduckgo_lite_results(query, max_results=max_results)

        parts: List[str] = []
        used_urls: List[str] = []
        for i, row in enumerate(lite_results, start=1):
            title = row.get("title") or f"Result {i}"
            snippet = row.get("snippet") or ""
            url = row.get("url") or ""
            block = f"--- Result {i}: {title} ---"
            if url:
                block += f"\nURL: {url}"
                used_urls.append(url)
            if snippet:
                block += f"\n{snippet}"
            if len(block.strip()) > 40:
                parts.append(block)

        # Enrich with first scrapeable page when snippets alone are thin
        if sum(len(p) for p in parts) < 400:
            for url in used_urls[:2]:
                page_text = self.scrape_url(url)
                if len(page_text.strip()) >= 200:
                    parts.append(f"--- Scraped page: {url} ---\n{page_text[:6000]}")
                    break

        combined = "\n\n".join(parts).strip()
        label = (company or "EXTERNAL").upper().strip() or "EXTERNAL"
        if not combined:
            return {
                "success": False,
                "source": f"Web Search (no results): {query[:80]}",
                "text": "",
                "company": label,
                "filing_type": "WEB",
                "search_query": query,
                "error": "No search snippets or pages returned",
            }

        return {
            "success": True,
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

    def _read_filing_text_from_dir(self, selected_dir: str, max_chars: int) -> str:
        for root, _, files in os.walk(selected_dir):
            for fname in files:
                if not fname.endswith((".txt", ".html")):
                    continue
                path = os.path.join(root, fname)
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    raw = fh.read()
                if fname.endswith(".html"):
                    text = BeautifulSoup(raw, "html.parser").get_text()
                else:
                    text = raw
                return " ".join(text.split())[:max_chars]
        return ""

    def fetch_sec_filings_multi(
        self,
        company: str,
        filing_type: str = "10-K",
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        """Download up to `limit` recent SEC filings and return text + inferred fiscal year."""
        ticker = self.resolve_ticker(company)
        actual_upper = (filing_type or "10-K").upper().strip() or "10-K"
        cap = max(1, min(int(limit), 8))
        logger.info("Fetching %s x%d for margin trends: %s (%s)", actual_upper, cap, company, ticker)

        try:
            from sec_edgar_downloader import Downloader

            dl = Downloader(
                self._sec_company,
                self._sec_email,
                self.download_dir,
            )
            count = dl.get(actual_upper.replace("-PRIOR", ""), ticker, limit=cap)
            if count <= 0:
                return []

            base = os.path.join(
                self.download_dir, "sec-edgar-filings", ticker, actual_upper.replace("-PRIOR", "")
            )
            if not os.path.isdir(base):
                return []

            subdirs = sorted(
                os.path.join(base, d)
                for d in os.listdir(base)
                if os.path.isdir(os.path.join(base, d))
            )
            selected = subdirs[-cap:]
            results: List[Dict[str, Any]] = []
            for selected_dir in selected:
                accession = os.path.basename(selected_dir)
                text = self._read_filing_text_from_dir(selected_dir, 50000)
                if not text:
                    continue
                from backend.extraction.margin_trends import (
                    extract_fiscal_year,
                    year_from_accession_dir,
                )

                fiscal_year = year_from_accession_dir(accession) or extract_fiscal_year(text)
                results.append(
                    {
                        "success": True,
                        "source": f"SEC EDGAR ({ticker} {actual_upper} {accession})",
                        "text": text,
                        "company": company,
                        "ticker": ticker,
                        "filing_type": actual_upper,
                        "year": fiscal_year,
                        "accession": accession,
                    }
                )
            logger.info("Retrieved %s historical filing(s) for %s", len(results), ticker)
            return results
        except Exception as e:
            logger.warning("Multi-year SEC fetch failed for %s: %s", ticker, e)
            return []

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
