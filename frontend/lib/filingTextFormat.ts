/**
 * Client-side mirror of backend narrative_format for already-cached filing sections.
 * New pipeline runs format on the server; this improves display without re-ingestion.
 */

const REGION_ROW_RE =
  /^(Americas|Europe|Greater China|Japan|Rest of Asia Pacific|Total net sales)\b/i;
const PERIOD_HEADER_RE =
  /(Three|Six|Nine|Twelve)\s+Months\s+Ended|Year\s+Ended|Quarter\s+Ended/i;
const DOLLAR_RE = /\$\s*[\d,]+/g;
const PERCENT_RE = /\b\d{1,3}\s*%/g;
const TABLE_INTRO_RE =
  /following\s+table|table\s+shows|table\s+below|summarized\s+in\s+the\s+following/i;
const VALUE_TOKEN_RE = /^\$?\s*[\d,]+\.?\d*\s*%?\s*$/;

function isTableishLine(line: string): boolean {
  const s = line.trim();
  if (!s) return false;
  if (REGION_ROW_RE.test(s)) return true;
  if (PERIOD_HEADER_RE.test(s)) return true;
  if (DOLLAR_RE.test(s)) return true;
  if (PERCENT_RE.test(s) && s.length < 24) return true;
  if (VALUE_TOKEN_RE.test(s) && s.length < 20) return true;
  const dollars = s.match(DOLLAR_RE) ?? [];
  if (dollars.length >= 2) return true;
  return false;
}

function isProseLine(line: string): boolean {
  const s = line.trim();
  if (!s || isTableishLine(line)) return false;
  if (s.length >= 80 && s.endsWith(".") && s.includes(" ")) return true;
  return (
    s.length >= 28 &&
    s.endsWith(".") &&
    s.includes(" ") &&
    /\b(increased|decreased|compared|during|primarily|driven)\b/i.test(s)
  );
}

function collectVerticalValues(lines: string[], start: number): { values: string[]; next: number } {
  const values: string[] = [];
  let i = start;
  if (i < lines.length && REGION_ROW_RE.test(lines[i].trim()) && !DOLLAR_RE.test(lines[i])) {
    i += 1;
  }
  while (i < lines.length) {
    const s = lines[i].trim();
    if (!s) {
      i += 1;
      continue;
    }
    if (REGION_ROW_RE.test(s) && values.length > 0) break;
    if (isProseLine(lines[i])) break;
    const dollars = s.match(DOLLAR_RE);
    const percents = s.match(PERCENT_RE);
    if (dollars?.length) values.push(...dollars);
    else if (percents?.length) values.push(...percents);
    else if (VALUE_TOKEN_RE.test(s)) values.push(s);
    else break;
    i += 1;
  }
  return { values, next: i };
}

function parseVerticalTable(lines: string[]): string[][] | null {
  const rows: string[][] = [];
  let i = 0;
  while (i < lines.length && !REGION_ROW_RE.test(lines[i].trim())) {
    i += 1;
  }
  while (i < lines.length) {
    const s = lines[i].trim();
    if (!s) {
      i += 1;
      continue;
    }
    const rm = s.match(REGION_ROW_RE);
    if (rm) {
      const label = rm[0].trim();
      const rest = s.slice(rm.index! + rm[0].length).trim();
      if (rest) {
        const dollars = rest.match(DOLLAR_RE) ?? [];
        const percents = rest.match(PERCENT_RE) ?? [];
        rows.push([label, ...dollars, ...percents]);
        i += 1;
        continue;
      }
      const valueStart = rest ? i : i + 1;
      const { values, next } = collectVerticalValues(lines, valueStart);
      i = values.length ? next : Math.max(next, valueStart + 1);
      if (values.length) rows.push([label, ...values]);
      else rows.push([label]);
      continue;
    }
    if (isProseLine(lines[i])) break;
    i += 1;
  }
  if (rows.length === 0 || Math.max(...rows.map((r) => r.length)) < 2) return null;
  return rows;
}

function rowsToMarkdown(rows: string[][]): string {
  let working = rows.map((r) => [...r]);
  if (working.length && REGION_ROW_RE.test(working[0][0] ?? "")) {
    const width = Math.max(...working.map((r) => r.length));
    working = [["Segment", ...Array.from({ length: width - 1 }, (_, i) => `Period ${i + 1}`)], ...working];
  }
  const width = Math.max(...working.map((r) => r.length));
  const pad = (row: string[]) => [...row, ...Array(width - row.length).fill("")];
  const esc = (c: string) => c.replace(/\|/g, "\\|").trim();
  const padded = working.map(pad);
  const header = padded[0];
  const body = padded.slice(1);
  const out = [
    `| ${header.map(esc).join(" | ")} |`,
    `| ${header.map(() => "---").join(" | ")} |`,
    ...body.map((row) => `| ${row.map(esc).join(" | ")} |`),
  ];
  return out.join("\n");
}

function formatTableBlock(lines: string[]): string {
  const vertical = parseVerticalTable(lines);
  if (vertical?.length) return rowsToMarkdown(vertical);
  const body = lines.map((l) => l.trimEnd()).filter((l) => l.trim()).join("\n");
  return `\`\`\`\n${body}\n\`\`\``;
}

export function formatFilingSectionText(text: string): string {
  if (!text?.trim()) return text;

  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  let tableHint = false;

  while (i < lines.length) {
    const line = lines[i];
    const stripped = line.trim();

    if (TABLE_INTRO_RE.test(stripped)) {
      tableHint = true;
      out.push(line);
      i += 1;
      continue;
    }

    if (isTableishLine(line) || (tableHint && stripped && !isProseLine(line))) {
      const blockStart = i;
      const block: string[] = [];
      while (i < lines.length) {
        const cur = lines[i];
        if (!cur.trim()) {
          if (block.length && i + 1 < lines.length && isTableishLine(lines[i + 1])) {
            i += 1;
            continue;
          }
          break;
        }
        if (block.length && isProseLine(cur)) break;
        if (block.length && !isTableishLine(cur) && !tableHint) break;
        if (!block.length && !isTableishLine(cur) && !tableHint) break;
        block.push(cur);
        i += 1;
      }
      const hasRegionRows = block.some((l) => {
        const s = l.trim();
        return REGION_ROW_RE.test(s) && (DOLLAR_RE.test(s) || PERCENT_RE.test(s) || !s.includes(" increased"));
      });
      if (block.length >= 3 || (block.length >= 2 && hasRegionRows)) {
        if (out.length && out[out.length - 1]?.trim()) out.push("");
        out.push(formatTableBlock(block));
        out.push("");
        tableHint = false;
        continue;
      }
      i = blockStart;
    }

    out.push(line);
    i += 1;
    if (!isTableishLine(line)) tableHint = false;
  }

  return out.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}
