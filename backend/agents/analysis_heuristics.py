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
