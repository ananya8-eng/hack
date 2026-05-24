"""
Map-reduce analysis for large quarterly/annual narrative filings (10-Q / 10-K).

Map: analyze each section chunk in context (MD&A prioritized).
Reduce: merge risks, sentiment, future challenges, scraping decision.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.agents.analysis_heuristics import (
    analyze_risk_heuristics,
    compute_sentiment_heuristics,
)
from backend.agents.llm_client import llm_client
from backend.config import get_settings
from backend.extraction.section_models import FilingSection
from backend.rag.chunking import split_text_into_chunks
from backend.tools.chroma_tool import chromadb_manager
from backend.tools.scrape_plan import build_heuristic_scrape_requests, normalize_scraping_decision

logger = logging.getLogger(__name__)


def _map_chunk_size() -> int:
    return get_settings().map_analysis_chunk_chars


def _max_map_passes() -> int:
    return get_settings().max_map_passes


def _split_section_text(text: str) -> List[str]:
    size = _map_chunk_size()
    overlap = min(400, size // 5)
    if len(text) <= size:
        return [text]
    return split_text_into_chunks(text, chunk_size=size, chunk_overlap=overlap)


def _retrieve_section_context(
    query: str, company_name: str, section_id: str, n_results: int = 3
) -> str:
    where = {"company": company_name, "section": section_id}
    chunks = chromadb_manager.query_similar_chunks(query, n_results=n_results, where=where)
    if not chunks:
        chunks = chromadb_manager.query_similar_chunks(query, n_results=n_results)
    parts: List[str] = []
    for item in chunks:
        parts.append(item.get("document", ""))
    return "\n".join(parts)[:2500]


def map_analyze_chunk(
    *,
    section: FilingSection,
    chunk_text: str,
    chunk_index: int,
    chunk_total: int,
    company_name: str,
    user_query: str,
) -> Dict[str, Any]:
    """Map pass: risks and sentiment signals from one section excerpt."""
    rag_query = user_query or "operational risks supply chain MD&A outlook sentiment"
    rag_ctx = _retrieve_section_context(rag_query, company_name, section.id)

    prompt = f"""
[System] You analyze narrative text from a public company earnings filing (10-Q/10-K).
Focus: operational risks, supply chain, regulatory issues, management tone, and forward challenges
that are NOT visible from balance-sheet numbers alone.

[Company] {company_name}
[Section] {section.title} (id={section.id}, priority={section.priority})
[Chunk] {chunk_index + 1} of {chunk_total}
[User focus] {user_query or "Earnings report risk and sentiment extraction"}

[Vector context]
{rag_ctx or "None"}

[Narrative excerpt]
{chunk_text}

[Task]
Return JSON only:
{{
  "section_id": "{section.id}",
  "section_title": "{section.title}",
  "risks": [
    {{
      "risk_name": "short title",
      "category": "Supply Chain | Competitive | Regulatory | Financial | Geopolitical | Operational",
      "severity": "High | Medium | Low",
      "evidence": "verbatim quote from excerpt",
      "implication": "business impact"
    }}
  ],
  "sentiment_signals": {{
    "classification": "Positive | Negative | Neutral",
    "score": -1.0 to 1.0,
    "optimism": 0-1,
    "pessimism": 0-1,
    "cautiousness": 0-1,
    "uncertainty": 0-1
  }},
  "future_challenges": ["specific forward risk or headwind from narrative"],
  "mda_highlights": ["key MD&A insight if this section is MD&A-related, else empty list"]
}}
"""
    parsed = llm_client.generate_json(prompt, temperature=0.1, timeout=75)
    if parsed:
        return parsed

    sent = compute_sentiment_heuristics(chunk_text)
    metrics = sent.get("metrics") or {}
    return {
        "section_id": section.id,
        "section_title": section.title,
        "risks": analyze_risk_heuristics(chunk_text),
        "sentiment_signals": {
            "classification": sent.get("classification"),
            "score": sent.get("score"),
            **metrics,
        },
        "future_challenges": [],
        "mda_highlights": [],
    }


_RISK_NAME_ALIASES = ("risk_name", "name", "title", "risk_title", "risk", "label")
_RISK_CATEGORY_ALIASES = ("category", "type", "risk_category", "risk_type", "domain")
_RISK_SEVERITY_ALIASES = ("severity", "level", "impact_level", "risk_level")
_RISK_EVIDENCE_ALIASES = ("evidence", "quote", "excerpt", "source_text", "supporting_text")
_RISK_IMPLICATION_ALIASES = (
    "implication",
    "implications",
    "impact",
    "business_impact",
    "description",
    "details",
    "explanation",
    "rationale",
)


def _first_present(payload: Dict[str, Any], keys: tuple) -> str:
    for k in keys:
        if k in payload and payload[k] is not None:
            val = payload[k]
            if isinstance(val, list):
                val = " ".join(str(item) for item in val if item)
            text = str(val).strip()
            if text:
                return text
    return ""


def _coerce_severity(raw: str) -> str:
    s = raw.strip().lower()
    if not s:
        return "Medium"
    if any(token in s for token in ("high", "severe", "critical", "major")):
        return "High"
    if any(token in s for token in ("low", "minor", "minimal")):
        return "Low"
    return "Medium"


def _normalize_risk_entry(risk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Map common LLM aliases onto the canonical risk schema used by the UI:
    {risk_name, category, severity, evidence, implication}.
    Returns None for entries that are unusable (no risk_name and no implication).
    """
    if not isinstance(risk, dict):
        return None

    name = _first_present(risk, _RISK_NAME_ALIASES)
    category = _first_present(risk, _RISK_CATEGORY_ALIASES) or "Operational"
    severity = _coerce_severity(_first_present(risk, _RISK_SEVERITY_ALIASES))
    evidence = _first_present(risk, _RISK_EVIDENCE_ALIASES)
    implication = _first_present(risk, _RISK_IMPLICATION_ALIASES)

    if not name and implication:
        # Synthesize a short title from the implication when LLM omitted a name.
        name = implication.split(".")[0][:80].strip()
    if not name:
        return None

    if not implication:
        implication = f"Operational or financial exposure related to {category.lower()}."

    return {
        "risk_name": name[:140],
        "category": category[:80],
        "severity": severity,
        "evidence": evidence[:500] if evidence else "",
        "implication": implication[:400],
    }


def _normalize_risk_list(raw_risks: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_risks, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for r in raw_risks:
        entry = _normalize_risk_entry(r)
        if entry:
            normalized.append(entry)
    return normalized


def _merge_risks(partials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    merged: List[Dict[str, Any]] = []
    for p in partials:
        for risk in _normalize_risk_list(p.get("risks")):
            key = risk["risk_name"].lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(risk)
    return merged[:25]


def _average_sentiment(partials: List[Dict[str, Any]]) -> Dict[str, Any]:
    scores: List[float] = []
    metrics = {"optimism": 0.0, "pessimism": 0.0, "cautiousness": 0.0, "uncertainty": 0.0}
    count = 0
    for p in partials:
        sig = p.get("sentiment_signals")
        if not isinstance(sig, dict):
            continue
        if "score" in sig:
            scores.append(float(sig["score"]))
        for k in metrics:
            if k in sig:
                metrics[k] += float(sig[k])
        count += 1
    if count:
        metrics = {k: round(v / count, 2) for k, v in metrics.items()}
    score = round(sum(scores) / len(scores), 2) if scores else 0.0
    classification = "Neutral"
    if score > 0.15:
        classification = "Positive"
    elif score < -0.15:
        classification = "Negative"
    return {
        "classification": classification,
        "score": score,
        "metrics": metrics,
    }


def reduce_partials(
    *,
    partials: List[Dict[str, Any]],
    sections: List[FilingSection],
    company_name: str,
    user_query: str,
    combined_excerpt: str,
) -> Dict[str, Any]:
    """Reduce pass: unified analysis + scrape decision."""
    risks = _merge_risks(partials)
    sentiment = _average_sentiment(partials)
    future_challenges: List[str] = []
    mda_highlights: List[str] = []
    for p in partials:
        for fc in p.get("future_challenges") or []:
            if isinstance(fc, str) and fc.strip() and fc not in future_challenges:
                future_challenges.append(fc.strip())
        for hl in p.get("mda_highlights") or []:
            if isinstance(hl, str) and hl.strip() and hl not in mda_highlights:
                mda_highlights.append(hl.strip())

    section_summary = [
        {"id": s.id, "title": s.title, "priority": s.priority, "chars": len(s.text)}
        for s in sections[:12]
    ]
    map_digest = json.dumps(
        {
            "risks_count": len(risks),
            "top_risks": [r.get("risk_name") for r in risks[:8]],
            "sentiment": sentiment,
            "future_challenges": future_challenges[:12],
            "mda_highlights": mda_highlights[:8],
        },
        indent=2,
    )[:5000]

    prompt = f"""
[System] You synthesize a hackathon-grade earnings narrative intelligence report.
Topic: Risk & Sentiment Extractor — surface hidden operational risks and negative tone shifts in MD&A
and related narrative, not raw financial statement tables.

[Company] {company_name}
[User request] {user_query or "Extract risks, sentiment shifts, and future challenges from quarterly filing narrative."}

[Discovered sections in this filing]
{json.dumps(section_summary, indent=2)}

[Map-reduce digest from all section chunks]
{map_digest}

[MD&A / narrative excerpt sample]
{combined_excerpt[:5000]}

[Task]
Return JSON only. The risks array MUST use exactly this object shape — do not invent alternative keys:
{{
  "risks": [
    {{
      "risk_name": "short title (required)",
      "category": "Supply Chain | Competitive | Regulatory | Financial | Geopolitical | Operational",
      "severity": "High | Medium | Low",
      "evidence": "verbatim quote from the filing",
      "implication": "concrete business impact"
    }}
  ],
  "sentiment": {{ "classification", "score", "metrics": {{ optimism, pessimism, cautiousness, uncertainty }} }},
  "executive_summary": "2-4 sentences for analysts — emphasize MD&A tone and non-obvious risks",
  "explainability": "why these risks matter vs headline numbers",
  "mda_summary": "focused MD&A takeaway (supply chain, demand, margins narrative)",
  "future_challenges": ["list of forward headwinds"],
  "sentiment_shift_notes": "e.g. more cautious vs prior tone if inferable",
  "needs_scraping": true/false,
  "reason": "",
  "scrape_requests": [...],
  "targets": []
}}
"""
    parsed = llm_client.generate_json(prompt, temperature=0.1, timeout=120)
    if parsed:
        normalized_parsed_risks = _normalize_risk_list(parsed.get("risks"))
        if normalized_parsed_risks:
            # Prefer LLM-refined risks, but back-fill missing entries from map-step risks
            # so the UI always has at least the deterministic findings.
            seen = {r["risk_name"].lower().strip() for r in normalized_parsed_risks}
            for r in risks:
                key = r["risk_name"].lower().strip()
                if key not in seen:
                    normalized_parsed_risks.append(r)
                    seen.add(key)
            parsed["risks"] = normalized_parsed_risks[:25]
        else:
            parsed["risks"] = risks
        if not parsed.get("sentiment"):
            parsed["sentiment"] = sentiment
        if not parsed.get("future_challenges"):
            parsed["future_challenges"] = future_challenges
        return parsed

    scrape = build_heuristic_scrape_requests(combined_excerpt, user_query, company_name)
    return {
        "risks": risks or analyze_risk_heuristics(combined_excerpt),
        "sentiment": sentiment
        if scores_else_sentiment(sentiment)
        else compute_sentiment_heuristics(combined_excerpt),
        "executive_summary": _fallback_summary(company_name, risks, sentiment, mda_highlights),
        "explainability": "Synthesized from map-reduce passes over all discovered narrative sections.",
        "mda_summary": " ".join(mda_highlights[:3]) or "See MD&A section in filing viewer.",
        "future_challenges": future_challenges[:10],
        "sentiment_shift_notes": "",
        "needs_scraping": scrape.get("needs_scraping", False),
        "reason": scrape.get("reason", ""),
        "scrape_requests": scrape.get("scrape_requests", []),
        "targets": scrape.get("targets", []),
    }


def scores_else_sentiment(sentiment: Dict[str, Any]) -> bool:
    return isinstance(sentiment, dict) and "score" in sentiment


def _fallback_summary(
    company: str, risks: List[dict], sentiment: Dict[str, Any], mda: List[str]
) -> str:
    n_high = sum(1 for r in risks if r.get("severity") == "High")
    tone = sentiment.get("classification", "Neutral")
    mda_bit = mda[0] if mda else "Review MD&A for management outlook."
    return (
        f"{company} narrative review ({tone}, score {sentiment.get('score', 0)}): "
        f"{len(risks)} risks ({n_high} high severity). {mda_bit}"
    )


def run_map_reduce_analysis(
    sections: List[FilingSection],
    company_name: str,
    user_query: str,
) -> Dict[str, Any]:
    """Execute map-reduce over discovered sections (MD&A and peers first)."""
    if not sections:
        raise ValueError("No sections provided for map-reduce analysis")

    ordered = sorted(sections, key=lambda s: (-s.priority, s.id))
    partials: List[Dict[str, Any]] = []
    map_passes = 0
    max_passes = _max_map_passes()

    for section in ordered:
        if section.priority < 15:
            continue
        chunks = _split_section_text(section.text)
        for i, chunk in enumerate(chunks):
            if map_passes >= max_passes:
                logger.info("Map pass cap reached (%s)", max_passes)
                break
            partial = map_analyze_chunk(
                section=section,
                chunk_text=chunk,
                chunk_index=i,
                chunk_total=len(chunks),
                company_name=company_name,
                user_query=user_query,
            )
            partials.append(partial)
            map_passes += 1
        if map_passes >= max_passes:
            break

    combined_parts: List[str] = []
    for s in ordered[:6]:
        combined_parts.append(f"=== {s.title} ===\n{s.text[:8000]}")
    combined_excerpt = "\n\n".join(combined_parts)

    reduced = reduce_partials(
        partials=partials,
        sections=sections,
        company_name=company_name,
        user_query=user_query,
        combined_excerpt=combined_excerpt,
    )
    return normalize_scraping_decision(reduced, combined_excerpt, user_query, company_name)
