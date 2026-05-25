"""Source typing and evidence checks for RAG / comparison chat citations."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# UI-facing labels
SOURCE_LABELS = {
    "uploaded_filing": "Uploaded filing PDF (vector DB / Qdrant)",
    "sec_edgar": "SEC EDGAR live scrape",
    "prior_filing": "Prior-period SEC filing scrape",
    "web_search": "Web search scrape",
}


def normalize_company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def companies_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    ka, kb = normalize_company_key(a), normalize_company_key(b)
    if not ka or not kb:
        return False
    if ka == kb or ka in kb or kb in ka:
        return True
    try:
        from backend.tools.scraper import financial_scraper

        ta = financial_scraper.resolve_ticker(a)
        tb = financial_scraper.resolve_ticker(b)
        if ta and tb and ta == tb:
            return True
    except Exception:
        pass
    return False


def classify_scraped_source(ctx: dict) -> str:
    """Classify an external scrape document for chat attribution."""
    filing_type = str(ctx.get("filing_type") or "").upper()
    source = str(ctx.get("source") or "").lower()
    if "prior" in filing_type or "prior period" in source:
        return "prior_filing"
    if "web search" in source or ctx.get("urls") or filing_type == "WEB":
        return "web_search"
    if "sec edgar" in source or filing_type in ("10-K", "10-Q", "8-K"):
        return "sec_edgar"
    return "web_search"


def citation_from_chroma_chunk(item: dict, index: int) -> dict:
    meta = item.get("metadata") or {}
    sec = str(meta.get("section", "Section")).replace("_", " ").title()
    comp = str(meta.get("company", "Company"))
    chunk_idx = meta.get("chunk_index", index)
    doc = str(item.get("document") or "")
    return {
        "citation_id": f"[{comp} {sec} — chunk {chunk_idx}]",
        "section": sec,
        "company": comp,
        "chunk_index": chunk_idx,
        "content": doc[:300] + ("..." if len(doc) > 300 else ""),
        "source_type": "uploaded_filing",
        "source_label": SOURCE_LABELS["uploaded_filing"],
    }


def citation_from_scraped_context(ctx: dict, index: int) -> dict:
    company = str(ctx.get("company") or "Peer")
    source = str(ctx.get("source") or "External")
    text = str(ctx.get("text") or "")
    stype = classify_scraped_source(ctx)
    return {
        "citation_id": f"[{company} — {SOURCE_LABELS[stype]}]",
        "section": "Peer / external context",
        "company": company,
        "chunk_index": index,
        "content": text[:300] + ("..." if len(text) > 300 else ""),
        "source": source,
        "source_type": stype,
        "source_label": SOURCE_LABELS[stype],
        "urls": ctx.get("urls") or [],
    }


def build_evidence_corpus(
    original_analysis: dict,
    scraped_contexts: List[dict],
    filing_excerpt: str = "",
) -> str:
    parts: List[str] = [filing_excerpt or ""]
    for risk in original_analysis.get("risks") or []:
        if isinstance(risk, dict):
            parts.append(str(risk.get("evidence") or ""))
            parts.append(str(risk.get("risk_name") or ""))
    parts.append(str(original_analysis.get("executive_summary") or ""))
    parts.append(str(original_analysis.get("explainability") or ""))
    for ctx in scraped_contexts:
        parts.append(str(ctx.get("text") or ""))
    return " ".join(parts)


def _numeric_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in re.finditer(
        r"\$?\s*[\d,]+(?:\.\d+)?\s*(?:%|percent|billion|million|bn|mm|bps)?",
        text,
        flags=re.I,
    ):
        raw = match.group(0)
        digits = re.sub(r"[^\d.]", "", raw)
        if len(digits) >= 2:
            tokens.add(digits)
    return tokens


def benchmark_supported_by_corpus(comparison_value: str, corpus: str) -> bool:
    """Reject benchmark lines whose dollar/% figures are absent from retrieved evidence."""
    value = (comparison_value or "").strip()
    if not value:
        return False
    claim_nums = _numeric_tokens(value)
    if not claim_nums:
        return True
    corpus_nums = _numeric_tokens(corpus)
    if not corpus_nums:
        return False
    return bool(claim_nums & corpus_nums)


def sanitize_competitor_benchmarks(
    benchmarks: List[dict],
    company_name: str,
    evidence_corpus: str,
) -> List[dict]:
    """Drop self-comparisons and metrics not grounded in retrieved text."""
    cleaned: List[dict] = []
    for bm in benchmarks or []:
        if not isinstance(bm, dict):
            continue
        peer = str(
            bm.get("competitor_company")
            or bm.get("comparison_target")
            or ""
        ).strip()
        if peer and companies_match(peer, company_name):
            continue
        value = str(bm.get("comparison_value") or "").strip()
        if value and not benchmark_supported_by_corpus(value, evidence_corpus):
            continue
        cleaned.append(bm)
    return cleaned


def summarize_source_types(citations: List[dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for cit in citations:
        st = str(cit.get("source_type") or "unknown")
        counts[st] = counts.get(st, 0) + 1
    return counts
