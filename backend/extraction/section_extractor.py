"""
Discover narrative sections per filing (10-Q / 10-K / earnings updates).

Strategy (full document, all pages):
  1. Regex heading index across entire text → slice sections (MD&A, Risk Factors, etc.)
  2. If sparse: LLM outline from compact heading catalog only
  3. Fallback: page-bounded or fixed-size narrative chunks with auto titles
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from backend.agents.llm_client import llm_client
from backend.extraction.heading_index import (
    build_heading_index,
    slice_sections_from_headings,
)
from backend.extraction.section_models import FilingSection

logger = logging.getLogger(__name__)

MIN_FILING_CHARS = 100
MIN_SECTION_CHARS = 120
MAX_SECTION_CHARS = 120_000
HEADING_CATALOG_LINES = 400
FALLBACK_CHUNK_CHARS = 12_000

_PAGE_MARKER_RE = re.compile(r"---\s*PAGE\s+(\d+)\s*---", re.IGNORECASE)


class SectionExtractionError(RuntimeError):
    """Raised when no usable narrative sections can be extracted."""


def _priority_boost_mda(sections: List[FilingSection]) -> List[FilingSection]:
    """Ensure MD&A-class sections rank highest for map-reduce analysis."""
    boosted: List[FilingSection] = []
    for s in sections:
        title_up = s.title.upper()
        pri = s.priority
        if "MANAGEMENT" in title_up and "DISCUSSION" in title_up:
            pri = max(pri, 100)
        elif "MD&A" in title_up or "RESULTS OF OPERATIONS" in title_up:
            pri = max(pri, 100)
        elif "ITEM 7" in title_up or ("ITEM 2" in title_up and "MANAGEMENT" in title_up):
            pri = max(pri, 100)
        boosted.append(
            FilingSection(
                id=s.id,
                title=s.title,
                text=s.text,
                priority=pri,
                source=s.source,
            )
        )
    return boosted


def _heading_catalog(full_text: str, max_lines: int = HEADING_CATALOG_LINES) -> str:
    """Compact outline for LLM: candidate lines that look like section headings."""
    lines: List[str] = []
    for line in full_text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) < 6:
            continue
        if len(stripped) > 200:
            continue
        upper_ratio = sum(1 for c in stripped if c.isupper()) / max(len(stripped), 1)
        if (
            re.search(r"ITEM\s+\d", stripped, re.I)
            or re.search(
                r"MANAGEMENT|RISK FACTOR|FORWARD|MD&A|RESULTS OF OPERATIONS|BUSINESS",
                stripped,
                re.I,
            )
            or (upper_ratio > 0.55 and len(stripped) < 120)
        ):
            lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return "\n".join(lines)


def _find_anchor(haystack: str, anchor: str) -> int:
    if not anchor or len(anchor.strip()) < 10:
        return -1
    anchor = anchor.strip()
    idx = haystack.find(anchor)
    if idx >= 0:
        return idx
    return haystack.lower().find(anchor.lower())


def _slice_by_anchors(
    full_text: str, outline: List[Dict[str, Any]], max_section_chars: int
) -> List[FilingSection]:
    sections: List[FilingSection] = []
    used_ids: Dict[str, int] = {}

    for entry in outline:
        title = str(entry.get("title") or entry.get("name") or "Section").strip()
        start = str(entry.get("start_anchor") or "").strip()
        end = str(entry.get("end_anchor") or "").strip()
        priority = int(entry.get("priority") or 50)
        if not start:
            continue
        start_idx = _find_anchor(full_text, start)
        if start_idx < 0:
            continue
        end_idx = len(full_text)
        if end:
            rel = _find_anchor(full_text[start_idx + 1 :], end)
            if rel >= 0:
                end_idx = start_idx + 1 + rel
        body = full_text[start_idx:end_idx].strip()
        if len(body) < MIN_SECTION_CHARS:
            continue
        if len(body) > max_section_chars:
            body = body[:max_section_chars].strip()

        sec_id = str(entry.get("id") or re.sub(r"[^a-z0-9]+", "_", title.lower())[:48])
        if sec_id in used_ids:
            used_ids[sec_id] += 1
            sec_id = f"{sec_id}_{used_ids[sec_id]}"
        else:
            used_ids[sec_id] = 1

        sections.append(
            FilingSection(
                id=sec_id,
                title=title,
                text=body,
                priority=priority,
                source="llm_outline",
            )
        )
    return sections


def _llm_discover_outline(catalog: str, total_chars: int) -> Optional[List[Dict[str, Any]]]:
    prompt = f"""
[System] You are an SEC filing structure analyst for quarterly (10-Q) and annual (10-K) earnings reports.

The hackathon focus is narrative text: especially Management's Discussion and Analysis (MD&A), risk factors,
forward-looking statements, and other sections that reveal operational risks and sentiment — not raw financial tables.

[Filing]
Total length: {total_chars} characters.
Below is a heading catalog (not the full body). Identify narrative sections present in THIS filing.

[Heading catalog]
{catalog}

[Task]
Return JSON only:
{{
  "filing_type_hint": "10-Q | 10-K | other",
  "sections": [
    {{
      "id": "snake_case_unique_id",
      "title": "Human-readable section title",
      "start_anchor": "40-120 char exact phrase from catalog where section begins",
      "end_anchor": "phrase where next section begins, or empty",
      "priority": 0-100 (100 = MD&A / Results of Operations, 95 = Risk Factors, 85 = forward-looking)
    }}
  ]
}}

Rules:
- Always include MD&A (Item 7 for 10-K, often Item 2 for 10-Q) if present in catalog.
- Include Risk Factors (Item 1A or Part II Item 1A for 10-Q) when present.
- Include forward-looking / cautionary language section when present.
- Omit financial statement tables (Item 8, balance sheets, notes).
- Use anchors that appear verbatim in the catalog.
- Sections must match THIS filing, not a generic template.
"""
    parsed = llm_client.generate_json(prompt, temperature=0.0, timeout=120)
    if not isinstance(parsed, dict):
        return None
    raw = parsed.get("sections")
    return raw if isinstance(raw, list) else None


def _fallback_page_chunks(full_text: str) -> List[FilingSection]:
    """Split on page markers or fixed windows when no headings found."""
    parts = _PAGE_MARKER_RE.split(full_text)
    sections: List[FilingSection] = []

    if len(parts) > 1:
        # parts alternates: [preamble, page_num, text, page_num, text, ...]
        i = 1
        while i < len(parts):
            page_label = parts[i]
            body = parts[i + 1] if i + 1 < len(parts) else ""
            i += 2
            body = body.strip()
            if len(body) < MIN_SECTION_CHARS:
                continue
            if len(body) > MAX_SECTION_CHARS:
                body = body[:MAX_SECTION_CHARS]
            sections.append(
                FilingSection(
                    id=f"page_{page_label}",
                    title=f"Filing excerpt (page {page_label})",
                    text=body,
                    priority=35,
                    source="fallback_chunk",
                )
            )
        if sections:
            return sections

    start = 0
    idx = 0
    while start < len(full_text):
        chunk = full_text[start : start + FALLBACK_CHUNK_CHARS].strip()
        if len(chunk) >= MIN_SECTION_CHARS:
            sections.append(
                FilingSection(
                    id=f"narrative_chunk_{idx}",
                    title=f"Narrative segment {idx + 1}",
                    text=chunk,
                    priority=30,
                    source="fallback_chunk",
                )
            )
            idx += 1
        start += FALLBACK_CHUNK_CHARS
    return sections


def discover_sections(full_text: str) -> List[FilingSection]:
    """
    Discover all narrative sections for this specific PDF filing.
    Raises SectionExtractionError if nothing usable is found.
    """
    if not full_text or len(full_text.strip()) < MIN_FILING_CHARS:
        raise SectionExtractionError("Filing text is too short for section discovery.")

    logger.info("Section discovery started (%s chars)", len(full_text))

    hits = build_heading_index(full_text)
    sliced = slice_sections_from_headings(full_text, hits, MAX_SECTION_CHARS)
    sections: List[FilingSection] = [
        FilingSection(id=s[0], title=s[1], text=s[2], priority=s[3], source=s[4])
        for s in sliced
    ]

    if len(sections) < 2:
        catalog = _heading_catalog(full_text)
        if catalog:
            outline = _llm_discover_outline(catalog, len(full_text))
            if outline:
                llm_sections = _slice_by_anchors(full_text, outline, MAX_SECTION_CHARS)
                if llm_sections:
                    sections = llm_sections
                    logger.info("Section discovery via LLM outline (%s sections)", len(sections))

    if not sections:
        sections = _fallback_page_chunks(full_text)
        logger.info("Section discovery via fallback chunks (%s sections)", len(sections))

    sections = _priority_boost_mda(sections)
    sections.sort(key=lambda s: (-s.priority, s.id))

    total_chars = sum(len(s.text) for s in sections)
    if total_chars < MIN_SECTION_CHARS:
        raise SectionExtractionError(
            "Could not extract usable narrative sections from this filing."
        )

    logger.info(
        "Section discovery complete: %s sections, %s chars (top: %s)",
        len(sections),
        total_chars,
        sections[0].title if sections else "n/a",
    )
    return sections


def extract_sections(text: str) -> Dict[str, str]:
    """
    Backward-compatible dict[id -> text] for callers expecting a mapping.
    """
    return {s.id: s.text for s in discover_sections(text)}


# Re-export for tests that import private helpers
def _slice_between(full_text: str, start_anchor: str, end_anchor: str) -> str:
    start = _find_anchor(full_text, start_anchor)
    if start < 0:
        return ""
    end = len(full_text)
    if end_anchor:
        end_idx = _find_anchor(full_text[start + 1 :], end_anchor)
        if end_idx >= 0:
            end = start + 1 + end_idx
    else:
        boundary = _next_item_boundary(full_text, start)
        if boundary is not None and boundary > start:
            end = boundary
    chunk = full_text[start:end].strip()
    if len(chunk) > MAX_SECTION_CHARS:
        chunk = chunk[:MAX_SECTION_CHARS].strip()
    return chunk


def _next_item_boundary(full_text: str, after_index: int) -> Optional[int]:
    pattern = re.compile(
        r"\n\s*ITEM\s+\d+[A-Z]?(?:\s*[\.\):\-–—])",
        re.IGNORECASE,
    )
    match = pattern.search(full_text, after_index + 1)
    return match.start() if match else None
