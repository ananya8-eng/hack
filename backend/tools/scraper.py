import os
import re
import datetime
import logging
from typing import Dict, Any

from backend.tools.sec_discovery import get_latest_filing_url
from backend.tools.tinyfish_client import tinyfish_client
from backend.tools.cache_manager import load_cached_response, save_cached_response

logger = logging.getLogger(__name__)

class FinancialScraper:
    def __init__(self):
        logger.info("FinancialScraper initialised (TinyFish mode)")

    def _clean_markdown(self, raw_md: str) -> str:
        """
        Cleans markdown to ensure it fits well into context windows.
        Removes excessive linebreaks and ensures a clean text representation.
        """
        # Basic cleanup - TinyFish already returns clean markdown, so we just do minimal tidying
        cleaned = re.sub(r'\n{3,}', '\n\n', raw_md)
        return cleaned.strip()

    def fetch_sec_filing(self, company: str, filing_type: str = "10-K") -> Dict[str, Any]:
        """
        Orchestrates the retrieval of a SEC filing via TinyFish.
        Follows this flow:
        1. Check cache
        2. Discover SEC URL via TinyFish
        3. Fetch and extract clean markdown via TinyFish
        4. Normalize and cache result
        5. Return structured filing object
        """
        company_clean = company.upper().strip()
        filing_type_clean = filing_type.upper().strip()
        
        logger.info(f"═══ Fetching {filing_type_clean} filing for {company_clean} via TinyFish ═══")

        # 1. Cache Check
        cached_data = load_cached_response(company_clean, filing_type_clean)
        if cached_data:
            logger.info(f"Returning cached filing for {company_clean} {filing_type_clean}")
            return cached_data

        # 2. Discover Filing URL
        discovery_meta = get_latest_filing_url(company_clean, filing_type_clean)
        if not discovery_meta:
            error_msg = f"Could not locate {filing_type_clean} filing for {company_clean} on SEC EDGAR via TinyFish"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "details": f"TinyFish search did not return a valid SEC filing for '{company_clean}'"
            }

        url = discovery_meta["url"]
        
        # 3. Fetch Filing Content
        fetch_result = tinyfish_client.fetch_clean_filing(url)
        if not fetch_result or not fetch_result.results:
            error_msg = f"Failed to extract content from {url}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "details": f"TinyFish fetch failed for {url}"
            }
            
        content_item = fetch_result.results[0]
        raw_markdown = content_item.markdown or content_item.text or ""
        
        if not raw_markdown:
            error_msg = f"No content extracted from {url}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "details": "TinyFish returned empty text/markdown for the URL"
            }

        # 4. Normalize and structure
        clean_text = self._clean_markdown(raw_markdown)
        
        # In a real pipeline we'd extract CIK and accession from the URL, but here we can just use placeholders or parse
        # Example URL: https://www.sec.gov/Archives/edgar/data/320193/000032019324000069/aapl-20230930.htm
        cik = "UNKNOWN"
        accession = "UNKNOWN"
        match = re.search(r"data/(\d+)/(\d+)", url)
        if match:
            cik = match.group(1).zfill(10)
            accession = match.group(2)
            # Format accession to include dashes if needed (e.g., 0000320193-24-000069)
            if len(accession) > 12:
                accession = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"

        structured_response = {
            "success": True,
            "company": company_clean,
            "filing_type": filing_type_clean,
            "filing_date": datetime.datetime.now().strftime("%Y-%m-%d"), # Since TinyFish discovery might not return exact date easily without LLM parse
            "source": f"SEC EDGAR ({company_clean} {filing_type_clean})",
            "url": url,
            "text": clean_text,
            "markdown": raw_markdown,
            "metadata": {
                "cik": cik,
                "accession": accession,
                "retrieved_at": datetime.datetime.now().isoformat()
            }
        }

        # 5. Save to Cache
        save_cached_response(company_clean, filing_type_clean, structured_response)
        
        logger.info(f"═══ Successfully retrieved {filing_type_clean} filing for {company_clean} (length: {len(clean_text)}) ═══")
        return structured_response

# Singleton instance
financial_scraper = FinancialScraper()
