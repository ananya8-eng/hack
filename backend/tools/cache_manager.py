import os
import json
import hashlib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scraped_filings", "cache", "tinyfish")

def _ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def _generate_cache_key(company: str, filing_type: str) -> str:
    # A simple key combining company and filing type, optionally hashed
    base_str = f"{company.upper()}_{filing_type.upper()}"
    hash_suffix = hashlib.md5(base_str.encode("utf-8")).hexdigest()[:8]
    return f"{base_str}_{hash_suffix}.json"

def load_cached_response(company: str, filing_type: str) -> Optional[Dict[str, Any]]:
    """Loads a cached TinyFish response for a given company and filing type."""
    _ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, _generate_cache_key(company, filing_type))
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Cache HIT for {company} {filing_type}")
            return data
        except Exception as e:
            logger.exception(f"Failed to read cache file {cache_file}: {e}")
            return None
            
    logger.info(f"Cache MISS for {company} {filing_type}")
    return None

def save_cached_response(company: str, filing_type: str, data: Dict[str, Any]) -> bool:
    """Saves a TinyFish response to cache."""
    _ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, _generate_cache_key(company, filing_type))
    
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Cached TinyFish response for {company} {filing_type} -> {cache_file}")
        return True
    except Exception as e:
        logger.exception(f"Failed to write cache file {cache_file}: {e}")
        return False
