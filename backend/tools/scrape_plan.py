"""Normalize LLM / heuristic scraping decisions into executable scrape requests."""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List

COMPARE_KEYWORDS = (
    "compare",
    "comparison",
    "competitor",
    "versus",
    " vs ",
    "against",
    "benchmark",
    "previous year",
    "historical",
    "trend",
    "peer",
    "prior year",
    "rival",
    "market share",
)


def _needs_external_context(user_query: str, text: str) -> bool:
    query_lower = (user_query or "").lower()
    text_lower = (text or "").lower()
    return any(w in query_lower or w in text_lower for w in COMPARE_KEYWORDS)


def is_comparison_query(user_query: str, filing_text: str = "") -> bool:
    """True when the user message should trigger peer scrape + comparative SLM."""
    return _needs_external_context(user_query, filing_text)


def extract_peer_companies(user_query: str, base_company: str) -> List[str]:
    """
    Pull explicit peer company names from natural-language comparison questions.
    """
    if not user_query:
        return []

    base_norm = re.sub(r"[^a-z0-9]", "", (base_company or "").lower())
    peers: List[str] = []
    seen: set[str] = set()

    patterns = [
        re.compile(
            r"(?:compare|benchmark|versus|vs\.?|against)\s+(?:\w+\s+){0,6}"
            r"(?:with|against|to|versus|vs\.?)\s+([A-Za-z][A-Za-z0-9&.\-\s]{1,40})",
            re.I,
        ),
        re.compile(
            r"(?:compare|benchmark)\s+([A-Za-z][A-Za-z0-9&.\-\s]{1,40})\s+"
            r"(?:with|against|to|versus|vs\.?)\s+([A-Za-z][A-Za-z0-9&.\-\s]{1,40})",
            re.I,
        ),
        re.compile(r"(?:peer|competitor|rival)\s+([A-Za-z][A-Za-z0-9&.\-\s]{1,40})", re.I),
    ]

    for pattern in patterns:
        for match in pattern.finditer(user_query):
            for group in match.groups():
                if not group:
                    continue
                name = re.split(
                    r"\s+(?:on|for|using|from|in|and|or|with|about)\s+",
                    group.strip(),
                    maxsplit=1,
                )[0].strip(" .,;:")
                if len(name) < 2:
                    continue
                norm = re.sub(r"[^a-z0-9]", "", name.lower())
                if not norm or norm == base_norm or norm in seen:
                    continue
                seen.add(norm)
                peers.append(name.title())

    return peers[:3]


def _coerce_request(raw: Any, company_name: str) -> Dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    req_type = str(raw.get("type") or "web_search").strip().lower()
    if req_type not in ("web_search", "sec_filing", "prior_filing"):
        req_type = "web_search"
    query = str(raw.get("query") or "").strip()
    company = str(raw.get("company") or company_name or "").strip()
    filing_type = str(raw.get("filing_type") or "10-K").strip().upper() or "10-K"
    purpose = str(raw.get("purpose") or "").strip()
    if req_type == "web_search" and not query:
        return None
    if req_type in ("sec_filing", "prior_filing") and not company:
        return None
    return {
        "type": req_type,
        "query": query,
        "company": company,
        "filing_type": filing_type,
        "purpose": purpose,
    }


def targets_to_requests(targets: List[str], company_name: str) -> List[Dict[str, Any]]:
    """Legacy ticker targets → structured requests."""
    requests: List[Dict[str, Any]] = []
    base = company_name.upper().strip()
    for target in targets:
        t = str(target).upper().strip()
        if not t:
            continue
        if t.endswith("_PRIOR") or t == f"{base}_PRIOR":
            requests.append(
                {
                    "type": "prior_filing",
                    "query": "",
                    "company": company_name,
                    "filing_type": "10-K",
                    "purpose": "Prior-period SEC filing for year-over-year comparison",
                }
            )
        else:
            requests.append(
                {
                    "type": "sec_filing",
                    "query": "",
                    "company": t,
                    "filing_type": "10-K",
                    "purpose": f"SEC filing for peer entity {t}",
                }
            )
    return requests


def build_heuristic_scrape_requests(
    text: str, user_query: str, company_name: str
) -> Dict[str, Any]:
    """Fallback when the LLM is unavailable: mirror the user's question only."""
    if not _needs_external_context(user_query, text):
        return {"needs_scraping": False, "reason": "", "scrape_requests": [], "targets": []}

    requests: List[Dict[str, Any]] = []
    query = (user_query or "").strip()
    if not query:
        return {
            "needs_scraping": False,
            "reason": "Comparison requires a specific question naming peers or metrics.",
            "scrape_requests": [],
            "targets": [],
        }

    requests.append(
        {
            "type": "web_search",
            "query": query,
            "company": company_name,
            "filing_type": "WEB",
            "purpose": "User-requested external financial context",
        }
    )

    query_lower = query.lower()
    if any(w in query_lower for w in ("previous year", "prior year", "historical", "yoy")):
        requests.append(
            {
                "type": "prior_filing",
                "query": "",
                "company": company_name,
                "filing_type": "10-K",
                "purpose": "Prior-period SEC filing",
            }
        )

    for peer in extract_peer_companies(user_query, company_name):
        requests.append(
            {
                "type": "sec_filing",
                "query": "",
                "company": peer,
                "filing_type": "10-K",
                "purpose": f"SEC filing for peer benchmark: {peer}",
            }
        )

    # De-duplicate by type+company+query
    deduped: List[Dict[str, Any]] = []
    seen_keys: set[tuple] = set()
    for req in requests:
        key = (
            req.get("type"),
            str(req.get("company", "")).upper(),
            str(req.get("query", "")).lower()[:80],
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(req)
    requests = deduped

    reason = "External enrichment required for comparison or peer context."
    return {
        "needs_scraping": bool(requests),
        "reason": reason,
        "scrape_requests": requests[:5],
        "targets": [],
    }


def plan_comparison_scrapes(
    user_query: str,
    company_name: str,
    filing_excerpt: str,
) -> Dict[str, Any]:
    """
    LLM-planned scrape targets for a chat comparison question.
    Falls back to query-only heuristics (no invented competitor list).
    """
    from backend.agents.llm_client import llm_client

    query = (user_query or "").strip()
    if not query:
        return {
            "needs_scraping": False,
            "reason": "Empty comparison question.",
            "scrape_requests": [],
            "targets": [],
        }

    prompt = f"""
[System] You plan external data fetches to answer ONE user comparison question about an SEC filing.

[Uploaded company]
{company_name}

[User question]
{query}

[Filing excerpt]
{(filing_excerpt or "")[:2500]}

[Rules]
- Only request sources needed to answer THIS question.
- Do NOT assume or inject competitor names unless the user or filing excerpt names them.
- Prefer web_search using the user's exact comparison intent as the query when discovery is needed.
- Use sec_filing only for companies explicitly named in the user question (resolve to tickers in scrape_requests).
- Use prior_filing only when the user asks for year-over-year / prior period on {company_name}.
- Maximum 5 scrape_requests.

Return strict JSON:
{{
  "needs_scraping": true,
  "reason": "short reason",
  "scrape_requests": [
    {{
      "type": "web_search | sec_filing | prior_filing",
      "query": "required for web_search — use the user's comparison wording",
      "company": "ticker or company label",
      "filing_type": "10-K | 10-Q | WEB",
      "purpose": "why this fetch answers the question"
    }}
  ],
  "targets": []
}}
"""

    parsed = llm_client.generate_json(prompt, temperature=0.1, timeout=60)
    if isinstance(parsed, dict):
        return normalize_scraping_decision(
            parsed, filing_excerpt or "", query, company_name
        )

    return build_heuristic_scrape_requests(filing_excerpt or "", query, company_name)


def normalize_scraping_decision(
    payload: dict, text: str, user_query: str, company_name: str
) -> dict:
    """Merge LLM output, legacy targets, and heuristics into scrape_requests."""
    needs = bool(payload.get("needs_scraping", False))
    if _needs_external_context(user_query, text):
        needs = True
    reason = str(payload.get("reason") or "").strip()

    raw_requests = payload.get("scrape_requests") or []
    requests: List[Dict[str, Any]] = []
    if isinstance(raw_requests, list):
        for item in raw_requests:
            coerced = _coerce_request(item, company_name)
            if coerced:
                requests.append(coerced)

    targets = payload.get("targets") or []
    if isinstance(targets, str):
        targets = [targets]
    legacy_targets = [str(t).strip().upper() for t in targets if str(t).strip()]
    if not requests and legacy_targets:
        requests = targets_to_requests(legacy_targets, company_name)

    if needs and not requests:
        fallback = build_heuristic_scrape_requests(text, user_query, company_name)
        requests = fallback.get("scrape_requests", [])
        reason = reason or fallback.get("reason", "")

    payload["needs_scraping"] = needs and bool(requests)
    payload["scrape_requests"] = requests[:5]
    payload["targets"] = legacy_targets[:3]
    payload["reason"] = reason
    return payload


def resolve_request_tickers(
    scrape_requests: List[Dict[str, Any]],
    resolve_ticker: Callable[[str], str],
) -> List[Dict[str, Any]]:
    """Resolve company fields to SEC tickers for filing fetches (immutable copy)."""
    resolved: List[Dict[str, Any]] = []
    for req in scrape_requests:
        item = dict(req)
        req_type = str(item.get("type") or "").lower()
        if req_type in ("sec_filing", "prior_filing"):
            company = str(item.get("company") or "").strip()
            if company:
                item["company"] = resolve_ticker(company)
        resolved.append(item)
    return resolved


def companies_from_requests(scrape_requests: List[Dict[str, Any]], target_company: str) -> List[str]:
    """Companies referenced in the scrape plan (for validator context)."""
    names = {target_company.upper().strip()}
    for req in scrape_requests:
        company = str(req.get("company") or "").strip()
        if company:
            names.add(company.upper())
    return sorted(names)
