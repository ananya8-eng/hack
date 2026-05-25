"""
Format extracted filing narrative text for display (markdown tables, readable blocks).

PDF text often flattens tables into one value per line or ragged columns; this module
detects those regions and emits GitHub-flavored markdown tables where possible.
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

# Segment / geography labels common in MD&A net-sales tables
_REGION_NAMES = (
    "Americas",
    "Europe",
    "Greater China",
    "Japan",
    "Rest of Asia Pacific",
    "Total net sales",
)
_REGION_ROW_RE = re.compile(
    r"^(" + "|".join(re.escape(n) for n in _REGION_NAMES) + r")(\s+.*)?$",
    re.IGNORECASE,
)


def _is_region_data_row(line: str) -> bool:
    """True when line is a geography/segment table row, not prose mentioning a region."""
    m = _REGION_ROW_RE.match(line.strip())
    if not m:
        return False
    rest = (m.group(2) or "").strip()
    if not rest:
        return True
    if _DOLLAR_RE.search(rest) or _PERCENT_RE.search(rest):
        return True
    if all(_VALUE_TOKEN_RE.match(tok) for tok in re.split(r"\s+", rest) if tok):
        return True
    return False
_PERIOD_HEADER_RE = re.compile(
    r"(Three|Six|Nine|Twelve)\s+Months\s+Ended|Year\s+Ended|Quarter\s+Ended",
    re.IGNORECASE,
)
_DATE_FRAGMENT_RE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*$",
    re.IGNORECASE,
)
_YEAR_LINE_RE = re.compile(r"^\d{4}\s*$")
_DOLLAR_RE = re.compile(r"\$\s*[\d,]+")
_PERCENT_RE = re.compile(r"\b\d{1,3}\s*%")
_CHANGE_RE = re.compile(r"^Change\s*$", re.IGNORECASE)
_VALUE_TOKEN_RE = re.compile(r"^\$?\s*[\d,]+\.?\d*\s*%?\s*$")
_TABLE_INTRO_RE = re.compile(
    r"following\s+table|table\s+shows|table\s+below|summarized\s+in\s+the\s+following",
    re.IGNORECASE,
)


def _is_tableish_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _is_region_data_row(stripped):
        return True
    if _PERIOD_HEADER_RE.search(stripped):
        return True
    if _DATE_FRAGMENT_RE.match(stripped):
        return True
    if _YEAR_LINE_RE.match(stripped):
        return True
    if _CHANGE_RE.match(stripped):
        return True
    if _DOLLAR_RE.search(stripped):
        return True
    if _PERCENT_RE.search(stripped) and len(stripped) < 24:
        return True
    if _VALUE_TOKEN_RE.match(stripped) and len(stripped) < 20:
        return True
    # Multiple financial tokens on one line (layout-preserved PDF row)
    if len(_DOLLAR_RE.findall(stripped)) >= 2:
        return True
    if len(_DOLLAR_RE.findall(stripped)) >= 1 and len(_PERCENT_RE.findall(stripped)) >= 1:
        return True
    return False


def _is_prose_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or _is_tableish_line(line):
        return False
    if len(stripped) >= 80 and stripped.endswith("."):
        alpha = sum(1 for c in stripped if c.isalpha())
        return alpha / max(len(stripped), 1) > 0.55
    # Narrative sentences after tables (often shorter than 80 chars)
    if (
        len(stripped) >= 28
        and stripped.endswith(".")
        and " " in stripped
        and re.search(r"\b(increased|decreased|compared|during|primarily|driven)\b", stripped, re.I)
    ):
        return True
    return False


def _split_row_cells(line: str) -> List[str]:
    stripped = line.strip()
    if not stripped:
        return []
    if "\t" in stripped:
        return [c.strip() for c in stripped.split("\t") if c.strip()]
    parts = re.split(r"\s{2,}", stripped)
    if len(parts) >= 3:
        return parts
    if _is_region_data_row(stripped):
        m = _REGION_ROW_RE.match(stripped)
        label = m.group(1).strip() if m else stripped
        rest = (m.group(2) or "").strip() if m else ""
        dollars = _DOLLAR_RE.findall(rest)
        percents = _PERCENT_RE.findall(rest)
        if dollars or percents:
            return [label, *dollars, *percents]
        return [label]
    dollars = _DOLLAR_RE.findall(stripped)
    percents = _PERCENT_RE.findall(stripped)
    if dollars or percents:
        return [*dollars, *percents]
    return [stripped]


def _collect_vertical_values(lines: List[str], start: int) -> Tuple[List[str], int]:
    """Collect $/% tokens from consecutive short lines after a region label."""
    values: List[str] = []
    i = start
    if i < len(lines) and _is_region_data_row(lines[i]) and not _DOLLAR_RE.search(lines[i]):
        i += 1
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if _is_region_data_row(s) and values:
            break
        if _is_prose_line(lines[i]):
            break
        if s == "$" and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if re.match(r"^[\d,]+", nxt):
                values.append(f"${nxt}")
                i += 2
                continue
        if _DOLLAR_RE.search(s):
            values.extend(_DOLLAR_RE.findall(s))
        elif _PERCENT_RE.search(s):
            values.extend(_PERCENT_RE.findall(s))
        elif _VALUE_TOKEN_RE.match(s):
            values.append(s)
        elif _PERIOD_HEADER_RE.search(s) and values:
            break
        else:
            break
        i += 1
    return values, i


def _parse_vertical_table_block(lines: List[str]) -> Optional[List[List[str]]]:
    """Parse tables where PDF put each cell on its own line."""
    rows: List[List[str]] = []
    i = 0
    header_lines: List[str] = []
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if _is_region_data_row(s):
            break
        header_lines.append(s)
        i += 1
    if not header_lines and not any(_is_region_data_row(l) for l in lines):
        return None

    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if _is_region_data_row(s):
            m = _REGION_ROW_RE.match(s)
            label = m.group(1).strip() if m else s
            rest = (m.group(2) or "").strip() if m else ""
            if rest:
                cells = _split_row_cells(s)
                if len(cells) > 1:
                    rows.append(cells)
                    i += 1
                    continue
            value_start = i if rest else i + 1
            values, i = _collect_vertical_values(lines, value_start)
            if values:
                rows.append([label, *values])
            else:
                rows.append([label])
                if value_start <= i:
                    i = max(i, value_start + 1)
            continue
        if _is_prose_line(lines[i]):
            break
        i += 1

    if not rows:
        return None
    max_cols = max(len(r) for r in rows)
    if max_cols < 2:
        return None
    return rows


def _parse_horizontal_table_block(lines: List[str]) -> Optional[List[List[str]]]:
    rows: List[List[str]] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if _is_prose_line(line):
            break
        cells = _split_row_cells(line)
        if cells:
            rows.append(cells)
    if len(rows) < 2:
        return None
    max_cols = max(len(r) for r in rows)
    if max_cols < 2:
        return None
    if not any(_is_region_data_row(r[0]) for r in rows if r):
        # require at least one data row or multi-column header
        if max_cols < 3 and not any(_PERIOD_HEADER_RE.search(" ".join(r)) for r in rows):
            return None
    return rows


def _rows_to_markdown(rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return ""
    working = [list(r) for r in rows]
    if working and _is_region_data_row(str(working[0][0])):
        width = max(len(r) for r in working)
        headers = ["Segment"] + [f"Period {i}" for i in range(1, width)]
        working = [headers] + working
    width = max(len(r) for r in working)
    padded = [list(r) + [""] * (width - len(r)) for r in working]
    def esc(cell: str) -> str:
        return cell.replace("|", "\\|").strip()

    header = padded[0]
    body = padded[1:] if len(padded) > 1 else []
    lines = [
        "| " + " | ".join(esc(c) for c in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(esc(c) for c in row) + " |")
    return "\n".join(lines)


def _format_table_block(lines: List[str]) -> str:
    vertical = _parse_vertical_table_block(lines)
    if vertical and len(vertical) >= 1:
        return _rows_to_markdown(vertical)
    horizontal = _parse_horizontal_table_block(lines)
    if horizontal:
        return _rows_to_markdown(horizontal)
    # Fallback: monospace block preserves alignment better than flowing text
    body = "\n".join(l.rstrip() for l in lines if l.strip())
    return f"```\n{body}\n```"


def format_narrative_text(text: str) -> str:
    """Convert flattened PDF table regions to markdown for UI / markdown renderers."""
    if not text or not text.strip():
        return text

    lines = text.splitlines()
    out: List[str] = []
    i = 0
    table_hint = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if _TABLE_INTRO_RE.search(stripped):
            table_hint = True
            out.append(line)
            i += 1
            continue

        if _is_tableish_line(line) or (
            table_hint and stripped and not _is_prose_line(line)
        ):
            block_start = i
            block: List[str] = []
            while i < len(lines):
                cur = lines[i]
                if not cur.strip():
                    if block and i + 1 < len(lines) and _is_tableish_line(lines[i + 1]):
                        i += 1
                        continue
                    break
                if block and _is_prose_line(cur):
                    break
                if (
                    block
                    and table_hint
                    and stripped
                    and not _is_tableish_line(cur)
                    and len(stripped) > 35
                ):
                    break
                if block and not _is_tableish_line(cur) and not table_hint:
                    break
                if not block and not _is_tableish_line(cur) and not table_hint:
                    break
                block.append(cur)
                i += 1
            has_region_rows = any(_is_region_data_row(l.strip()) for l in block)
            if len(block) >= 3 or (len(block) >= 2 and has_region_rows):
                if out and out[-1].strip():
                    out.append("")
                out.append(_format_table_block(block))
                out.append("")
                table_hint = False
                continue
            i = block_start

        out.append(line)
        i += 1
        if not _is_tableish_line(line):
            table_hint = False

    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()
