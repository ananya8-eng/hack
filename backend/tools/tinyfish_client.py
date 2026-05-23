import os
import logging
from typing import Dict, Any, Optional
from tinyfish import TinyFish

logger = logging.getLogger(__name__)

class MockSearchResult:
    def __init__(self, url):
        self.url = url

class MockSearchQueryResponse:
    def __init__(self, urls):
        self.results = [MockSearchResult(url) for url in urls]

class MockContentItem:
    def __init__(self, markdown):
        self.markdown = markdown
        self.text = markdown

class MockFetchResponse:
    def __init__(self, markdown):
        self.results = [MockContentItem(markdown)]

class TinyFishClient:
    def __init__(self):
        self.api_key = os.environ.get("TINYFISH_API_KEY")
        self.is_mock = False
        if not self.api_key:
            logger.warning("TINYFISH_API_KEY environment variable is not set. Using mocked responses.")
            self.api_key = "mock"
            self.is_mock = True
        self.client = TinyFish(api_key=self.api_key)

    def search_web(self, query: str) -> Optional[Any]:
        """
        Executes a web search using TinyFish.
        """
        logger.info(f"TinyFish Search Request: '{query}'")
        if self.is_mock:
            # Mock discovering SEC filing URL
            return MockSearchQueryResponse(["https://www.sec.gov/Archives/edgar/data/0000000000/000000000024000000/mock-filing.htm"])
            
        try:
            result = self.client.search.query(query=query)
            logger.info("TinyFish Search Request completed successfully.")
            return result
        except Exception as e:
            logger.exception(f"TinyFish search failed for query: '{query}'")
            return None

    def fetch_url(self, url: str) -> Optional[Any]:
        """
        Fetches and extracts clean markdown from a URL using TinyFish.
        """
        logger.info(f"TinyFish Fetch Request: '{url}'")
        if self.is_mock:
            return MockFetchResponse("# Mocked SEC Filing Content\n\nThis is a mocked response to prove the pipeline is fully connected via TinyFish structure.")
            
        try:
            result = self.client.fetch.get_contents(urls=[url], format="markdown")
            logger.info(f"TinyFish Fetch Request completed successfully for {url}.")
            return result
        except Exception as e:
            logger.exception(f"TinyFish fetch failed for URL: '{url}'")
            return None

    def search_sec_filing(self, company: str, filing_type: str) -> Optional[Any]:
        """
        Specific helper to search for SEC filings.
        """
        query = f"{company} latest {filing_type} SEC filing site:sec.gov/Archives/edgar/data"
        return self.search_web(query)

    def fetch_clean_filing(self, url: str) -> Optional[Any]:
        """
        Specific helper to fetch and clean a filing URL.
        """
        return self.fetch_url(url)

tinyfish_client = TinyFishClient()
