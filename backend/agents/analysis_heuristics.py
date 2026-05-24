"""Heuristic risk and sentiment analysis when LLM map/reduce is unavailable."""
from __future__ import annotations

import re
from typing import List


def compute_sentiment_heuristics(text: str) -> dict:
    text_lower = text.lower()
    positive_words = [
        "increase", "growth", "strong", "record", "optimistic", "expand",
        "profit", "gain", "improve", "successful", "demand", "momentum",
    ]
    negative_words = [
        "decline", "decrease", "risk", "uncertainty", "cautious", "adversely",
        "loss", "shortage", "strain", "disruption", "weak", "challenge", "threat",
    ]
    cautious_words = [
        "cautious", "careful", "monitoring", "prudent", "challenges",
        "headwinds", "volatility", "mitigate",
    ]
    uncertain_words = [
        "uncertain", "unpredictable", "fluctuate", "may", "might", "could", "depend",
    ]

    pos_count = sum(len(re.findall(rf"\b{w}\b", text_lower)) for w in positive_words)
    neg_count = sum(len(re.findall(rf"\b{w}\b", text_lower)) for w in negative_words)
    caut_count = sum(len(re.findall(rf"\b{w}\b", text_lower)) for w in cautious_words)
    unc_count = sum(len(re.findall(rf"\b{w}\b", text_lower)) for w in uncertain_words)
    total_words = len(text_lower.split()) or 1

    optimism = min(1.0, (pos_count / total_words) * 200)
    pessimism = min(1.0, (neg_count / total_words) * 150)
    cautiousness = min(1.0, (caut_count / total_words) * 150)
    uncertainty = min(1.0, (unc_count / total_words) * 125)

    sentiment_score = max(-1.0, min(1.0, optimism - pessimism - uncertainty * 0.1))
    classification = "Neutral"
    if sentiment_score > 0.15:
        classification = "Positive"
    elif sentiment_score < -0.15:
        classification = "Negative"

    return {
        "classification": classification,
        "score": round(sentiment_score, 2),
        "metrics": {
            "optimism": round(optimism, 2),
            "pessimism": round(pessimism, 2),
            "cautiousness": round(cautiousness, 2),
            "uncertainty": round(uncertainty, 2),
        },
    }


def analyze_risk_heuristics(text: str) -> List[dict]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    risks: List[dict] = []
    risk_categories = {
        "Supply Chain": ["supply chain", "shortage", "logistics", "manufacturing"],
        "Competitive": ["competitor", "market share", "pricing pressure", "competition"],
        "Regulatory": ["export control", "regulation", "tariff", "compliance"],
        "Financial": ["liquidity", "debt", "margin", "revenue decline"],
        "Geopolitical": ["geopolitical", "international trade", "sanctions"],
    }
    found_names: set[str] = set()

    for sentence in sentences:
        sentence_clean = sentence.strip()
        if len(sentence_clean) < 40:
            continue
        for category, keywords in risk_categories.items():
            if any(w in sentence_clean.lower() for w in keywords):
                title = f"{category} Exposure"
                if title in found_names or len(risks) >= 8:
                    break
                found_names.add(title)
                severity = "Medium"
                if any(w in sentence_clean.lower() for w in ("severe", "material", "adverse")):
                    severity = "High"
                risks.append({
                    "risk_name": title,
                    "category": category,
                    "severity": severity,
                    "evidence": sentence_clean,
                    "implication": f"Operational or financial pressure under {category.lower()}.",
                })
                break

    if not risks:
        risks.append({
            "risk_name": "Macroeconomic And Demand Uncertainty",
            "category": "Financial",
            "severity": "Medium",
            "evidence": (sentences[0][:200] if sentences else text[:200]),
            "implication": "Narrative cites broader market volatility affecting outlook.",
        })
    return risks


def _term_density(text: str, terms: tuple[str, ...]) -> int:
    lower = (text or "").lower()
    return sum(lower.count(term) for term in terms)


def _snippet_for_query(text: str, user_query: str, max_len: int = 400) -> str:
    """Return the best-matching sentence from retrieved text for the user's question."""
    if not text:
        return ""
    keywords = [
        w.strip("?,.!")
        for w in (user_query or "").lower().split()
        if len(w) > 3
    ]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        lower = sentence.lower()
        if keywords and any(k in lower for k in keywords):
            return sentence.strip()[:max_len]
    return (sentences[0].strip()[:max_len] if sentences else text[:max_len])


def comparative_analysis_from_contexts(
    original_analysis: dict,
    scraped_contexts: list,
    company_name: str,
    user_query: str = "",
) -> dict:
    """
    Evidence-only comparative output derived from uploaded analysis + scraped text.
    No preset peers, tickers, or canned benchmark numbers.
    """
    risk_terms = (
        "risk", "supply", "competition", "regulatory", "uncertainty",
        "shortage", "margin", "revenue", "litigation", "cyber",
    )
    tone_terms = (
        "cautious", "optimistic", "growth", "decline", "uncertain",
        "confident", "adverse", "favorable", "headwind", "tailwind",
    )

    orig_parts: List[str] = []
    for risk in original_analysis.get("risks") or []:
        if isinstance(risk, dict):
            orig_parts.append(str(risk.get("evidence") or ""))
            orig_parts.append(str(risk.get("risk_name") or ""))
    orig_parts.append(str(original_analysis.get("executive_summary") or ""))
    orig_text = " ".join(orig_parts)
    orig_risk_density = _term_density(orig_text, risk_terms)
    orig_tone_density = _term_density(orig_text, tone_terms)

    benchmarks: List[dict] = []
    tone_shifts: List[dict] = []
    summary_parts: List[str] = []

    for ctx in scraped_contexts:
        peer_label = str(ctx.get("company") or ctx.get("source") or "Retrieved peer").strip()
        peer_text = str(ctx.get("text") or "")
        peer_risk_density = _term_density(peer_text, risk_terms)
        peer_tone_density = _term_density(peer_text, tone_terms)

        benchmarks.append(
            {
                "metric_name": "Risk-term density (retrieved excerpt)",
                "target_company": company_name,
                "competitor_company": peer_label,
                "comparison_value": (
                    f"{company_name}: {orig_risk_density} occurrences vs "
                    f"{peer_label}: {peer_risk_density} in validated scrape sample"
                ),
            }
        )
        benchmarks.append(
            {
                "metric_name": "Tone-term density (retrieved excerpt)",
                "target_company": company_name,
                "competitor_company": peer_label,
                "comparison_value": (
                    f"{company_name}: {orig_tone_density} vs {peer_label}: {peer_tone_density}"
                ),
            }
        )

        if peer_tone_density > orig_tone_density:
            direction = "More cautionary / adverse language in peer excerpt"
        elif peer_tone_density < orig_tone_density:
            direction = "Less cautionary language in peer excerpt vs filing"
        else:
            direction = "Similar tone-term density"

        tone_shifts.append(
            {
                "comparison_target": peer_label,
                "shift_direction": direction,
                "details": _snippet_for_query(peer_text, user_query),
            }
        )
        summary_parts.append(
            f"Benchmarked {company_name} against {peer_label} using "
            f"{len(peer_text)} characters of validated external text."
        )

    question = (user_query or "").strip() or "peer comparison"
    comparative_analysis = (
        f"Comparison driven by your question: \"{question}\". "
        + " ".join(summary_parts)
        + " All figures above are counted from retrieved filing text only."
    )

    return {
        "original_summary": str(original_analysis.get("executive_summary") or ""),
        "comparative_analysis": comparative_analysis,
        "tone_shifts": tone_shifts,
        "competitor_benchmarks": benchmarks,
        "explainability_synthesis": (
            "Operational risk framing should be read alongside the exact excerpts "
            "retrieved for this query; no static peer assumptions were applied."
        ),
    }
