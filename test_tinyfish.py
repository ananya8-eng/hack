import logging
import sys
from backend.tools.scraper import financial_scraper

# Setup logging to see the output
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

print("Starting TinyFish Scraping Test")
print("==============================")

try:
    result = financial_scraper.fetch_sec_filing("AMD", "10-K")
    print(f"Success: {result.get('success')}")
    if result.get("success"):
        print(f"Source: {result.get('source')}")
        print(f"URL: {result.get('url')}")
        print(f"Text length: {len(result.get('text', ''))}")
        print(f"Metadata: {result.get('metadata')}")
    else:
        print(f"Error: {result.get('error')}")
        print(f"Details: {result.get('details')}")
except Exception as e:
    print(f"Test failed with exception: {e}")
