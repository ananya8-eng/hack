import logging
from typing import Optional, Dict, Any
from backend.tools.tinyfish_client import tinyfish_client

logger = logging.getLogger(__name__)

def build_sec_query(company: str, filing_type: str, year: Optional[str] = None) -> str:
    """Builds a natural language query for TinyFish to find SEC filings."""
    query = f"{company} {filing_type} SEC filing site:sec.gov/Archives/edgar/data"
    if year:
        query = f"{company} {year} {filing_type} SEC filing site:sec.gov/Archives/edgar/data"
    return query

def get_latest_filing_url(company: str, filing_type: str) -> Optional[Dict[str, Any]]:
    """
    Uses TinyFish to discover the latest SEC filing URL for a company.
    Returns metadata dict containing url, company, type, etc.
    """
    query = build_sec_query(company, filing_type)
    logger.info(f"Discovering latest filing for {company} ({filing_type}) via TinyFish")
    
    result = tinyfish_client.search_web(query)
    if not result or not result.results:
        logger.error(f"No search results found for query: {query}")
        return None
        
    for item in result.results:
        url = item.url
        if "sec.gov/Archives/edgar/data" in url and (url.endswith(".htm") or url.endswith(".txt")):
            logger.info(f"Discovered SEC filing URL: {url}")
            return {
                "url": url,
                "company": company,
                "filing_type": filing_type,
                "discovery_query": query
            }
            
    logger.error("Search completed but no valid SEC EDGAR URL was found in the top results.")
    return None

def get_historical_filing_urls(company: str, filing_type: str, year: str) -> Optional[Dict[str, Any]]:
    """
    Uses TinyFish to discover a historical SEC filing URL.
    """
    query = build_sec_query(company, filing_type, year)
    logger.info(f"Discovering historical filing for {company} ({filing_type}, {year}) via TinyFish")
    
    result = tinyfish_client.search_web(query)
    if not result or not result.results:
        return None
        
    for item in result.results:
        url = item.url
        if "sec.gov/Archives/edgar/data" in url and (url.endswith(".htm") or url.endswith(".txt")):
            return {
                "url": url,
                "company": company,
                "filing_type": filing_type,
                "year": year
            }
            
    return None
