"""
Self-reasoning / self-healing loops for financial analysis and web scraping.

When tool execution fails or outputs are invalid, the LLM revises plans using
observed errors and retries up to max_heal_attempts.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from backend.agents.llm_client import llm_client
from backend.config import get_settings
from backend.tools.scrape_plan import normalize_scraping_decision

logger = logging.getLogger(__name__)


def _max_attempts() -> int:
    return max(1, get_settings().max_heal_attempts)


def _failure_summary(failures: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for i, item in enumerate(failures, start=1):
        req = item.get("request") or {}
        err = item.get("error") or item.get("message") or "unknown error"
        lines.append(
            f"{i}. type={req.get('type')}, company={req.get('company')}, "
            f"query={str(req.get('query', ''))[:80]}, error={err}"
        )
    return "\n".join(lines) if lines else "No failures recorded."


def revise_scrape_requests(
    *,
    company_name: str,
    user_query: str,
    original_requests: List[Dict[str, Any]],
    failures: List[Dict[str, Any]],
    filing_excerpt: str = "",
    attempt: int = 1,
) -> List[Dict[str, Any]]:
    """
    LLM revises scrape_requests after tool failures (e.g. invalid ticker APPLE → AAPL).
    """
    prompt = f"""
[System] You are a financial data orchestration agent that repairs failed scrape plans.

[Context]
Primary company (uploaded filing): {company_name}
User request: {user_query or "General financial intelligence analysis"}
Heal attempt: {attempt} of {_max_attempts()}

[Original scrape_requests]
{json.dumps(original_requests, indent=2)}

[Tool failures — read carefully and fix root causes]
{_failure_summary(failures)}

[Filing excerpt for grounding]
{(filing_excerpt or "")[:2000]}

[Rules]
- For sec_filing and prior_filing, "company" MUST be a valid SEC ticker (e.g. AAPL not APPLE, GOOGL not GOOGLE).
- Resolve brand names to tickers: Apple → AAPL, Microsoft → MSFT, Amazon → AMZN, Alphabet/Google → GOOGL, Meta/Facebook → META.
- web_search requests need a concrete natural-language "query"; company can be a label.
- Do not repeat requests that already failed without correcting the underlying issue.
- Prefer web_search first for competitor discovery, then sec_filing with correct tickers.

[Task]
Return JSON only:
{{
  "reasoning": "Brief explanation of what went wrong and how you fixed it",
  "scrape_requests": [
    {{
      "type": "web_search | sec_filing | prior_filing",
      "query": "for web_search only",
      "company": "valid SEC ticker or descriptive label for web_search",
      "filing_type": "10-K | 10-Q | WEB",
      "purpose": "why this fetch helps"
    }}
  ]
}}
"""
    parsed = llm_client.generate_json(prompt, temperature=0.0, timeout=90)
    if not parsed:
        logger.warning("Heal scrape plan: LLM did not return JSON on attempt %s", attempt)
        return []

    reasoning = str(parsed.get("reasoning") or "").strip()
    if reasoning:
        logger.info("Heal scrape reasoning: %s", reasoning[:200])

    raw_requests = parsed.get("scrape_requests")
    if not isinstance(raw_requests, list) or not raw_requests:
        return []

    normalized = normalize_scraping_decision(
        {"needs_scraping": True, "scrape_requests": raw_requests, "reason": reasoning},
        filing_excerpt,
        user_query,
        company_name,
    )
    return list(normalized.get("scrape_requests") or [])


def revise_financial_analysis(
    *,
    company_name: str,
    user_query: str,
    filing_text: str,
    previous_analysis: Dict[str, Any],
    issues: List[str],
    attempt: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    LLM re-runs or patches financial analysis when validation finds gaps.
    """
    prompt = f"""
[System] You are an elite financial analyst repairing an incomplete or inconsistent analysis.

[Company] {company_name}
[User request] {user_query or "Full risk and sentiment audit"}

[Issues to fix]
{chr(10).join(f"- {issue}" for issue in issues)}

[Previous analysis]
{json.dumps(previous_analysis, indent=2)[:6000]}

[Filing text]
{filing_text[:4000]}

[Task]
Return the same JSON schema as a full financial analysis (risks, sentiment, executive_summary,
explainability, needs_scraping, reason, scrape_requests). Fix all listed issues.
Use valid SEC tickers in scrape_requests (AAPL not APPLE).
"""
    parsed = llm_client.generate_json(prompt, temperature=0.1, timeout=90)
    if parsed:
        logger.info("Financial analysis healed on attempt %s", attempt)
    return parsed


def validate_analysis_for_healing(analysis: Dict[str, Any]) -> List[str]:
    """Deterministic pre-flight checks before scraping."""
    issues: List[str] = []

    if not isinstance(analysis.get("risks"), list) or not analysis.get("risks"):
        issues.append("Missing or empty risks array.")

    sentiment = analysis.get("sentiment")
    if not isinstance(sentiment, dict) or "score" not in sentiment:
        issues.append("Missing or invalid sentiment object.")

    if not str(analysis.get("executive_summary") or "").strip():
        issues.append("Missing executive_summary.")

    if analysis.get("needs_scraping"):
        requests = analysis.get("scrape_requests") or []
        if not requests:
            issues.append("needs_scraping is true but scrape_requests is empty.")
        for i, req in enumerate(requests):
            if not isinstance(req, dict):
                issues.append(f"scrape_requests[{i}] is not an object.")
                continue
            req_type = str(req.get("type") or "").lower()
            if req_type in ("sec_filing", "prior_filing"):
                company = str(req.get("company") or "").strip().upper()
                if len(company) > 5 or company in ("APPLE", "GOOGLE", "AMAZON", "FACEBOOK", "MICROSOFT"):
                    issues.append(
                        f"scrape_requests[{i}] uses '{company}' — use SEC ticker (e.g. AAPL, GOOGL)."
                    )

    return issues


def run_scrape_with_healing(
    scrape_requests: List[Dict[str, Any]],
    *,
    execute_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    company_name: str,
    user_query: str,
    filing_excerpt: str = "",
    on_attempt: Optional[Callable[[int, str], None]] = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Execute scrape requests with LLM-driven self-correction on failure.

    Returns (successful_results, remaining_failures, heal_logs).
    """
    max_attempts = _max_attempts()
    heal_logs: List[str] = []
    results: List[Dict[str, Any]] = []
    pending = list(scrape_requests)
    all_failures: List[Dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        if not pending:
            break

        failures: List[Dict[str, Any]] = []
        for req in pending:
            res = execute_fn(req)
            if res.get("success"):
                results.append(res)
            else:
                error_msg = res.get("error") or res.get("source") or "scrape failed"
                failures.append(
                    {
                        "request": req,
                        "result": res,
                        "error": str(error_msg),
                    }
                )

        all_failures = failures
        if not failures:
            heal_logs.append(f"Scrape heal attempt {attempt}: all requests succeeded.")
            break

        heal_logs.append(
            f"Scrape heal attempt {attempt}: {len(failures)} failure(s); invoking LLM revision."
        )
        if on_attempt:
            on_attempt(attempt, heal_logs[-1])

        if attempt >= max_attempts:
            break

        revised = revise_scrape_requests(
            company_name=company_name,
            user_query=user_query,
            original_requests=pending,
            failures=failures,
            filing_excerpt=filing_excerpt,
            attempt=attempt + 1,
        )
        if not revised:
            heal_logs.append(f"Scrape heal attempt {attempt}: LLM returned no revised plan.")
            break

        pending = revised
        heal_logs.append(
            f"Scrape heal attempt {attempt}: retrying {len(pending)} revised request(s)."
        )

    return results, all_failures, heal_logs


def run_analysis_with_healing(
    analyze_fn: Callable[[], Dict[str, Any]],
    *,
    company_name: str,
    user_query: str,
    filing_text: str,
    shape_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    on_attempt: Optional[Callable[[int, str], None]] = None,
) -> tuple[Dict[str, Any], List[str]]:
    """
    Run financial analysis; if output fails validation, LLM heals and retries.

    Returns (analysis, heal_logs).
    """
    max_attempts = _max_attempts()
    heal_logs: List[str] = []
    analysis = analyze_fn()

    for attempt in range(1, max_attempts + 1):
        issues = validate_analysis_for_healing(analysis)
        if not issues:
            if attempt > 1:
                heal_logs.append(f"Analysis heal attempt {attempt}: validation passed.")
            return shape_fn(analysis), heal_logs

        heal_logs.append(
            f"Analysis heal attempt {attempt}: {len(issues)} issue(s) — {issues[0][:80]}"
        )
        if on_attempt:
            on_attempt(attempt, heal_logs[-1])

        if attempt >= max_attempts:
            heal_logs.append("Analysis heal: max attempts reached; using best-effort output.")
            return shape_fn(analysis), heal_logs

        healed = revise_financial_analysis(
            company_name=company_name,
            user_query=user_query,
            filing_text=filing_text,
            previous_analysis=analysis,
            issues=issues,
            attempt=attempt + 1,
        )
        if healed:
            analysis = healed
        else:
            heal_logs.append(f"Analysis heal attempt {attempt}: LLM heal failed; stopping.")
            break

    return shape_fn(analysis), heal_logs


def run_comparative_with_healing(
    analyze_fn: Callable[[], Dict[str, Any]],
    *,
    min_comparative_chars: int = 50,
    on_attempt: Optional[Callable[[int, str], None]] = None,
) -> tuple[Dict[str, Any], List[str]]:
    """Retry comparative analysis when output is missing or too thin."""
    max_attempts = _max_attempts()
    heal_logs: List[str] = []
    result = analyze_fn()

    for attempt in range(1, max_attempts + 1):
        comp = str(result.get("comparative_analysis") or "").strip()
        if len(comp) >= min_comparative_chars:
            return result, heal_logs

        issue = "comparative_analysis missing or too short"
        heal_logs.append(f"Comparative heal attempt {attempt}: {issue}")
        if on_attempt:
            on_attempt(attempt, heal_logs[-1])

        if attempt >= max_attempts:
            break

        retry = analyze_fn()
        if retry:
            result = retry

    return result, heal_logs
