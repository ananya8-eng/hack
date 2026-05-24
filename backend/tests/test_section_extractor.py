"""Unit tests for PDF-specific section discovery."""
from backend.extraction.heading_index import build_heading_index, slice_sections_from_headings
from backend.extraction.section_extractor import (
    MAX_SECTION_CHARS,
    _next_item_boundary,
    _slice_between,
    discover_sections,
)


def test_slice_between_respects_item_boundary_when_end_anchor_missing():
    filing = (
        "Preamble text.\n"
        "ITEM 7. MANAGEMENT'S DISCUSSION\n"
        "Revenue grew strongly in data center.\n"
        "ITEM 8. FINANCIAL STATEMENTS\n"
        "Balance sheet follows."
    )
    chunk = _slice_between(
        filing,
        "ITEM 7. MANAGEMENT'S DISCUSSION",
        "",
    )
    assert "Revenue grew" in chunk
    assert "Balance sheet" not in chunk
    assert "ITEM 8" not in chunk


def test_slice_between_caps_oversized_section():
    start = "ITEM 7. MD&A\n" + ("x" * (MAX_SECTION_CHARS + 500))
    filing = start + "\nITEM 8. FINANCIAL STATEMENTS\n"
    chunk = _slice_between(filing, "ITEM 7. MD&A", "")
    assert len(chunk) <= MAX_SECTION_CHARS


def test_next_item_boundary_finds_following_item():
    text = "ITEM 1A. RISK\nrisks here.\nITEM 7. MD&A\nnarrative.\nITEM 8. FINANCIAL\n"
    pos = _next_item_boundary(text, text.find("ITEM 7"))
    assert pos is not None
    assert text[pos : pos + 8].upper().startswith("\nITEM 8")


def test_discover_sections_10q_style_filing():
    filing = (
        "PART I\n"
        "ITEM 1A. RISK FACTORS\n"
        "We face supply chain concentration and export controls.\n"
        "ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION\n"
        "Revenue increased 12% driven by cloud demand but margins faced headwinds.\n"
        "ITEM 3. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK\n"
        "Interest rate sensitivity may affect debt costs.\n"
        "ITEM 4. CONTROLS AND PROCEDURES\n"
        "Disclosure controls were effective.\n"
    )
    sections = discover_sections(filing)
    ids = {s.id for s in sections}
    titles = " ".join(s.title.upper() for s in sections)
    assert len(sections) >= 2
    assert any("MD&A" in t or "MANAGEMENT" in t or "ITEM 2" in t for t in titles.split())
    assert any(s.priority >= 90 for s in sections)


def test_heading_index_finds_mda_and_risk():
    text = (
        "ITEM 1A. RISK FACTORS\n"
        + ("Supply chain and export control risks may materially affect operations. " * 3)
        + "\nITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS\n"
        + ("Revenue growth in cloud services continued though margins faced headwinds. " * 3)
        + "\n"
    )
    hits = build_heading_index(text)
    sliced = slice_sections_from_headings(text, hits, MAX_SECTION_CHARS)
    assert len(sliced) >= 2
