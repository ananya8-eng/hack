"""Extract multi-year gross margin trends from SEC filings and uploaded text."""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from backend.agents.analysis_heuristics import compute_sentiment_heuristics

logger = logging.getLogger(__name__)

_GROSS_MARGIN_PATTERNS = [
    re.compile(
        r"gross\s+margin(?:s)?\s+"
        r"(?:was|were|of|reached|expanded\s+to|declined\s+to|increased\s+to|decreased\s+to|"
        r"improved\s+to|approx(?:imately)?\.?)\s*"
        r"(?:about\s*)?(\d{1,2}(?:\.\d{1,2})?)\s*%",
        re.I,
    ),
    re.compile(r"gross\s+margin(?:s)?\s+of\s+(\d{1,2}(?:\.\d{1,2})?)\s*%", re.I),
    re.compile(r"(\d{1,2}(?:\.\d{1,2})?)\s*%\s+gross\s+margin", re.I),
]

_FISCAL_YEAR_PATTERNS = [
    re.compile(r"fiscal\s+year\s+ended.{0,80}?(\d{4})", re.I | re.DOTALL),
    re.compile(r"for\s+the\s+year\s+ended.{0,80}?(\d{4})", re.I | re.DOTALL),
    re.compile(r"year\s+ended.{0,80}?(\d{4})", re.I | re.DOTALL),
]


def year_from_accession_dir(dirname: str) -> Optional[str]:
    """Map SEC accession folder (e.g. 0000320193-24-000123) to calendar year."""
    match = re.search(r"-(\d{2})-", dirname)
    if not match:
        return None
    yy = int(match.group(1))
    return str(2000 + yy if yy < 80 else 1900 + yy)


def extract_fiscal_year(text: str) -> Optional[str]:
    if not text:
        return None
    head = text[:12000]
    for pattern in _FISCAL_YEAR_PATTERNS:
        match = pattern.search(head)
        if match:
            year = match.group(1)
            if 1995 <= int(year) <= 2035:
                return year
    return None


def extract_gross_margin_percent(text: str) -> Optional[float]:
    """Best-effort gross margin % from narrative or financial discussion text."""
    if not text:
        return None

    snippet = text[:100_000]
    values: List[float] = []
    for pattern in _GROSS_MARGIN_PATTERNS:
        for match in pattern.finditer(snippet):
            try:
                val = float(match.group(1))
            except ValueError:
                continue
            if 1.0 <= val <= 100.0:
                values.append(val)

    if not values:
        return None

    counts: Dict[float, int] = {}
    for val in values:
        counts[val] = counts.get(val, 0) + 1
    return max(counts, key=counts.get)


def _series_from_filings(filings: List[Dict[str, Any]]) -> Dict[str, float]:
    series: Dict[str, float] = {}
    for entry in filings:
        text = str(entry.get("text") or "")
        year = str(entry.get("year") or "").strip() or extract_fiscal_year(text)
        if not year:
            continue
        margin = extract_gross_margin_percent(text)
        if margin is not None:
            series[year] = margin
    return series


def compute_margin_trends(
    company_name: str,
    *,
    peer_company: Optional[str] = None,
    uploaded_text: str = "",
    fetch_filings_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    years: int = 4,
) -> Dict[str, Any]:
    """
    Build aligned year-over-year gross margin points for the target and optional peer.
    Data is sourced from SEC EDGAR 10-K history; uploaded text fills the latest gap if needed.
    """
    from backend.tools.scraper import financial_scraper

    fetch = fetch_filings_fn or financial_scraper.fetch_sec_filings_multi
    target_filings = fetch(company_name, filing_type="10-K", limit=years)
    target_series = _series_from_filings(target_filings)

    if uploaded_text.strip():
        upload_year = extract_fiscal_year(uploaded_text)
        upload_margin = extract_gross_margin_percent(uploaded_text)
        if upload_year and upload_margin is not None:
            target_series[upload_year] = upload_margin
        elif upload_margin is not None and target_filings:
            latest_year = str(target_filings[-1].get("year") or "")
            if latest_year:
                target_series[latest_year] = upload_margin

    peer_series: Dict[str, float] = {}
    peer_filings: List[Dict[str, Any]] = []
    peer_label = (peer_company or "").strip()

    if peer_label:
        peer_filings = fetch(peer_label, filing_type="10-K", limit=years)
        peer_series = _series_from_filings(peer_filings)

    all_years = sorted(set(target_series) | set(peer_series))
    points: List[Dict[str, Any]] = []
    for year in all_years:
        row: Dict[str, Any] = {"year": year}
        if year in target_series:
            row["target"] = target_series[year]
        if year in peer_series:
            row["peer"] = peer_series[year]
        if row.get("target") is not None or row.get("peer") is not None:
            points.append(row)

    peer_sentiment: Optional[Dict[str, Any]] = None
    if peer_filings:
        latest_text = str(peer_filings[-1].get("text") or "")
        if len(latest_text) > 500:
            peer_sentiment = compute_sentiment_heuristics(latest_text)

    if not points:
        logger.info(
            "No gross margin series extracted for %s (peer=%s)",
            company_name,
            peer_label or "none",
        )

    return {
        "target_label": company_name,
        "peer_label": peer_label or "Peer",
        "points": points,
        "peer_sentiment": peer_sentiment,
        "source": "sec_edgar_10k",
    }
