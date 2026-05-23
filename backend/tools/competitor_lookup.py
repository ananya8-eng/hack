"""
competitor_lookup.py
====================
Provides structured competitor/peer mappings for financial companies.

Each sector group maps a ticker to its direct industry competitors,
enabling the LangGraph pipeline to automatically identify which peers
to fetch filings for during comparative analysis.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# ─── Peer Mappings ────────────────────────────────────────────────────────────
# Organised by industry sector. Each ticker maps to a list of peer tickers.
# These are real public-company tickers used for SEC EDGAR lookups.

_SEMICONDUCTOR_PEERS: Dict[str, List[str]] = {
    "NVDA": ["AMD", "INTC", "AVGO"],
    "AMD":  ["NVDA", "INTC", "QCOM"],
    "INTC": ["AMD", "NVDA", "TXN"],
    "AVGO": ["NVDA", "QCOM", "TXN"],
    "QCOM": ["AVGO", "AMD", "MRVL"],
    "TXN":  ["ADI", "INTC", "AVGO"],
    "TSM":  ["INTC", "UMC", "GFS"],
    "MRVL": ["AVGO", "QCOM", "AMD"],
    "ADI":  ["TXN", "MCHP", "ON"],
    "MU":   ["WDC", "STX", "INTC"],
}

_BIG_TECH_PEERS: Dict[str, List[str]] = {
    "AAPL": ["MSFT", "GOOGL", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "AMZN"],
    "GOOGL": ["MSFT", "META", "AMZN"],
    "GOOG": ["MSFT", "META", "AMZN"],
    "AMZN": ["MSFT", "GOOGL", "AAPL"],
    "META": ["GOOGL", "SNAP", "PINS"],
}

_EV_AND_AUTO_PEERS: Dict[str, List[str]] = {
    "TSLA": ["F", "GM", "RIVN"],
    "RIVN": ["TSLA", "LCID", "F"],
    "F":    ["GM", "TSLA", "TM"],
    "GM":   ["F", "TSLA", "TM"],
}

_FINTECH_PEERS: Dict[str, List[str]] = {
    "V":    ["MA", "PYPL", "SQ"],
    "MA":   ["V", "PYPL", "AXP"],
    "PYPL": ["V", "MA", "SQ"],
    "SQ":   ["PYPL", "V", "AFRM"],
}

_CLOUD_SOFTWARE_PEERS: Dict[str, List[str]] = {
    "CRM":  ["NOW", "WDAY", "ORCL"],
    "NOW":  ["CRM", "WDAY", "SNOW"],
    "SNOW": ["DDOG", "MDB", "NOW"],
    "DDOG": ["SNOW", "SPLK", "ESTC"],
}

# ─── Combined Lookup Table ───────────────────────────────────────────────────
_ALL_PEERS: Dict[str, List[str]] = {}
for _sector_map in [
    _SEMICONDUCTOR_PEERS,
    _BIG_TECH_PEERS,
    _EV_AND_AUTO_PEERS,
    _FINTECH_PEERS,
    _CLOUD_SOFTWARE_PEERS,
]:
    _ALL_PEERS.update(_sector_map)


# ─── Public API ───────────────────────────────────────────────────────────────

def get_competitors(ticker: str, limit: int = 2) -> List[str]:
    """
    Return a list of competitor tickers for the given company.

    Args:
        ticker: Stock ticker (e.g. "NVDA").
        limit:  Maximum number of competitors to return (default 2).

    Returns:
        List of competitor ticker strings, or an empty list if no mapping exists.
    """
    ticker_upper = ticker.upper().strip()

    peers = _ALL_PEERS.get(ticker_upper, [])
    result = peers[:limit]

    if result:
        logger.info("Competitor lookup for %s → %s", ticker_upper, result)
    else:
        logger.info("No predefined competitors found for ticker %s", ticker_upper)

    return result


def get_sector_for_ticker(ticker: str) -> str:
    """
    Identify which sector a ticker belongs to, based on peer mappings.

    Returns:
        Sector name string, or "Unknown" if the ticker is not in any mapping.
    """
    ticker_upper = ticker.upper().strip()

    sector_map = {
        "Semiconductor": _SEMICONDUCTOR_PEERS,
        "Big Tech": _BIG_TECH_PEERS,
        "EV & Automotive": _EV_AND_AUTO_PEERS,
        "Fintech": _FINTECH_PEERS,
        "Cloud & Software": _CLOUD_SOFTWARE_PEERS,
    }

    for sector_name, peers_dict in sector_map.items():
        if ticker_upper in peers_dict:
            return sector_name

    return "Unknown"
