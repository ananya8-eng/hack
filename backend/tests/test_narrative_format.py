"""Tests for narrative table formatting."""
from backend.extraction.narrative_format import format_narrative_text


def test_format_segment_sales_table_vertical_cells():
    raw = """
Segment Operating Performance
The following table shows net sales by reportable segment for the three- and six-month periods ended March 28, 2026 and March 29,
2025 (dollars in millions):
Three Months Ended
Six Months Ended
March 28,
2026
March 29,
2025
Change
March 28,
2026
March 29,
2025
Change
Americas
$
45,093
$
40,315
12 %
$
103,622
$
92,963
11 %
Europe
28,055
24,454
15 %
66,201
58,315
14 %
Total net sales
$
111,184
$
95,359
17 %
$
254,940
$
219,659
16 %
Americas net sales increased during the second quarter.
""".strip()

    formatted = format_narrative_text(raw)
    assert "|" in formatted
    assert "Americas" in formatted
    assert "$45,093" in formatted or "45,093" in formatted
    assert "Americas net sales increased" in formatted


def test_format_preserves_prose_without_tables():
    prose = (
        "We face supply chain concentration and export controls that may "
        "materially affect our operations in multiple geographies."
    )
    assert format_narrative_text(prose) == prose


def test_format_horizontal_table_row():
    raw = """
The following table shows net sales (dollars in millions):
Americas  $45,093  $40,315  12%  $103,622  $92,963  11%
Europe  $28,055  $24,454  15%  $66,201  $58,315  14%
""".strip()
    formatted = format_narrative_text(raw)
    assert "| Americas |" in formatted or "| Americas |" in formatted
