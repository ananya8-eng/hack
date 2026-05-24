"""
Build a heading index across the full filing text (all pages) for section boundaries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

# US 10-K / 10-Q style ITEM headings and common narrative titles
_ITEM_HEADING_RE = re.compile(
    r"(?m)^\s*((?:PART\s+[IVXLC]+[\s\.–—-]*)?ITEM\s+\d+[A-Z]?(?:\s*[\.\):\-–—])?\s*[^\n]{0,160})",
    re.IGNORECASE,
)

_NARRATIVE_TITLE_RE = re.compile(
    r"(?m)^\s*((?:MANAGEMENT['\u2019]?S\s+DISCUSSION\s+AND\s+ANALYSIS"
    r"|MD\s*&\s*A"
    r"|RESULTS\s+OF\s+OPERATIONS"
    r"|RISK\s+FACTORS"
    r"|FORWARD[-\s]LOOKING\s+STATEMENTS?"
    r"|QUANTITATIVE\s+AND\s+QUALITATIVE\s+DISCLOSURES?"
    r"|CONTROLS\s+AND\s+PROCEDURES"
    r"|LEGAL\s+PROCEEDINGS"
    r"|BUSINESS\s+OVERVIEW)[^\n]{0,80})",
    re.IGNORECASE,
)

# Skip pure financial statement tables (low narrative value for risk/sentiment)
_LOW_VALUE_MARKERS = (
    "FINANCIAL STATEMENTS",
    "BALANCE SHEET",
    "STATEMENTS OF INCOME",
    "STATEMENTS OF CASH FLOWS",
    "NOTES TO CONSOLIDATED",
    "EXHIBIT INDEX",
    "SIGNATURES",
)


@dataclass(frozen=True)
class HeadingHit:
    position: int
    title: str
    suggested_id: str
    priority: int


def _slugify(title: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return raw[:64] or "section"


def _priority_for_title(title: str) -> int:
    t = title.upper()
    if "MANAGEMENT" in t and "DISCUSSION" in t or "MD&A" in t or "RESULTS OF OPERATIONS" in t:
        return 100
    if "ITEM 7" in t or "ITEM 2" in t and "MANAGEMENT" in t:  # 10-Q MD&A often Item 2
        return 100
    if "RISK FACTOR" in t or "ITEM 1A" in t:
        return 95
    if "FORWARD" in t and "LOOK" in t:
        return 85
    if "QUANTITATIVE" in t and "QUALITATIVE" in t:
        return 75
    if "CONTROLS" in t and "PROCEDURES" in t:
        return 70
    if "LEGAL PROCEED" in t:
        return 65
    if "BUSINESS" in t:
        return 60
    if "ITEM 1" in t and "BUSINESS" in t:
        return 55
    if any(m in t for m in _LOW_VALUE_MARKERS):
        return 10
    if "ITEM 8" in t or "ITEM 6" in t and "FINANCIAL" in t:
        return 5
    return 40


def _is_low_value(title: str) -> bool:
    t = title.upper()
    return any(m in t for m in _LOW_VALUE_MARKERS)


def build_heading_index(full_text: str) -> List[HeadingHit]:
    """Scan entire filing and return ordered heading hits."""
    hits: List[HeadingHit] = []
    seen_positions: set[int] = set()

    for pattern in (_ITEM_HEADING_RE, _NARRATIVE_TITLE_RE):
        for match in pattern.finditer(full_text):
            pos = match.start()
            if pos in seen_positions:
                continue
            title = match.group(1).strip()
            if len(title) < 8:
                continue
            if _is_low_value(title):
                continue
            seen_positions.add(pos)
            hits.append(
                HeadingHit(
                    position=pos,
                    title=title,
                    suggested_id=_slugify(title),
                    priority=_priority_for_title(title),
                )
            )

    hits.sort(key=lambda h: h.position)
    return _dedupe_nearby(hits)


def _dedupe_nearby(hits: List[HeadingHit], min_gap: int = 80) -> List[HeadingHit]:
    if not hits:
        return []
    out = [hits[0]]
    for h in hits[1:]:
        if h.position - out[-1].position < min_gap:
            if h.priority > out[-1].priority:
                out[-1] = h
            continue
        out.append(h)
    return out


def slice_sections_from_headings(
    full_text: str, hits: List[HeadingHit], max_section_chars: int
) -> List[Tuple[str, str, str, int, str]]:
    """
    Returns list of (id, title, text, priority, source).
    """
    if not hits:
        return []

    sections: List[Tuple[str, str, str, int, str]] = []
    used_ids: dict[str, int] = {}

    for i, hit in enumerate(hits):
        end = hits[i + 1].position if i + 1 < len(hits) else len(full_text)
        body = full_text[hit.position : end].strip()
        if len(body) < 120:
            continue
        if len(body) > max_section_chars:
            body = body[:max_section_chars].strip()

        sec_id = hit.suggested_id
        if sec_id in used_ids:
            used_ids[sec_id] += 1
            sec_id = f"{sec_id}_{used_ids[sec_id]}"
        else:
            used_ids[sec_id] = 1

        sections.append((sec_id, hit.title, body, hit.priority, "item_heading"))

    return sections
