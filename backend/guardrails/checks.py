"""Deterministic guardrail checks."""
from __future__ import annotations

import re
from typing import Iterable, List, Literal

from backend.guardrails.policies import (
    FINANCIAL_DISCLAIMER,
    FINANCIAL_SCOPE_TERMS,
    FOLLOW_UP_TERMS,
    HARMFUL_PATTERNS,
    INJECTION_PATTERNS,
    INVESTMENT_ADVICE_PATTERNS,
    PII_PATTERNS,
    SECRET_PATTERNS,
)
from backend.guardrails.types import GuardrailResult, GuardrailViolation

Channel = Literal["chat", "upload_query", "llm_prompt", "llm_output", "json_field"]


def _violations_from_patterns(
    text: str,
    patterns: Iterable[re.Pattern[str]],
    code_prefix: str,
    message: str,
) -> List[GuardrailViolation]:
    found: List[GuardrailViolation] = []
    for idx, pattern in enumerate(patterns):
        if pattern.search(text):
            found.append(
                GuardrailViolation(
                    code=f"{code_prefix}_{idx}",
                    message=message,
                    severity="block",
                )
            )
            break
    return found


def _pii_violations(text: str) -> List[GuardrailViolation]:
    violations: List[GuardrailViolation] = []
    for name, pattern in PII_PATTERNS:
        if pattern.search(text):
            violations.append(
                GuardrailViolation(
                    code=f"pii_{name}",
                    message="Input appears to contain sensitive personal data (PII). Remove it and retry.",
                    severity="block",
                )
            )
    return violations


def _in_scope_financial(text: str, channel: Channel) -> bool:
    lower = text.lower()
    if any(term in lower for term in FINANCIAL_SCOPE_TERMS):
        return True
    if channel == "chat" and any(term in lower for term in FOLLOW_UP_TERMS):
        if len(lower.split()) <= 24:
            return True
    if channel == "upload_query":
        # Upload instructions are usually extraction/analysis requests
        return any(
            w in lower
            for w in ("extract", "analyze", "analysis", "risk", "sentiment", "filing", "md&a")
        )
    return False


def check_text(
    text: str,
    *,
    channel: Channel,
    max_chars: int,
    require_financial_scope: bool = True,
) -> GuardrailResult:
    """Validate user-facing or model text."""
    stripped = (text or "").strip()
    violations: List[GuardrailViolation] = []

    if not stripped:
        violations.append(
            GuardrailViolation(
                code="empty_input",
                message="Message cannot be empty.",
                severity="block",
            )
        )
        return GuardrailResult.blocked(violations)

    if len(stripped) > max_chars:
        violations.append(
            GuardrailViolation(
                code="input_too_long",
                message=f"Input exceeds maximum length ({max_chars} characters).",
                severity="block",
            )
        )

    violations.extend(
        _violations_from_patterns(
            stripped,
            INJECTION_PATTERNS,
            "prompt_injection",
            "Potential prompt-injection pattern detected. Rephrase your question about the filing only.",
        )
    )
    violations.extend(
        _violations_from_patterns(
            stripped,
            HARMFUL_PATTERNS,
            "harmful_content",
            "This request cannot be processed.",
        )
    )
    violations.extend(_pii_violations(stripped))

    if channel in ("chat", "upload_query") and require_financial_scope:
        if not _in_scope_financial(stripped, channel):
            violations.append(
                GuardrailViolation(
                    code="off_topic",
                    message=(
                        "This assistant only answers questions about uploaded SEC filings "
                        "(risks, MD&A, sentiment, peer comparison, metrics in the narrative)."
                    ),
                    severity="block",
                )
            )

    if channel == "llm_output":
        violations.extend(
            _violations_from_patterns(
                stripped,
                SECRET_PATTERNS,
                "secret_leak",
                "Response blocked: possible secret or credential content.",
            )
        )

    if violations:
        return GuardrailResult.blocked(violations)

    return GuardrailResult.ok(stripped)


def sanitize_llm_output(text: str, *, max_chars: int) -> GuardrailResult:
    """Post-process model text: block secrets/PII, trim length, add disclaimer if needed."""
    stripped = (text or "").strip()
    if not stripped:
        return GuardrailResult.ok("")

    violations: List[GuardrailViolation] = []
    violations.extend(
        _violations_from_patterns(
            stripped,
            SECRET_PATTERNS,
            "secret_leak",
            "Response blocked: possible secret or credential content.",
        )
    )
    violations.extend(_pii_violations(stripped))
    if violations:
        return GuardrailResult.blocked(violations)

    sanitized = stripped
    if len(sanitized) > max_chars:
        sanitized = sanitized[: max_chars - 80].rstrip() + "\n\n[Response truncated for length.]"

    needs_disclaimer = any(p.search(sanitized) for p in INVESTMENT_ADVICE_PATTERNS)
    if needs_disclaimer and FINANCIAL_DISCLAIMER.strip() not in sanitized:
        sanitized = sanitized + FINANCIAL_DISCLAIMER

    return GuardrailResult.ok(sanitized)


def check_json_value(value, *, path: str = "$") -> List[GuardrailViolation]:
    """Recursively scan JSON structures for unsafe string content."""
    violations: List[GuardrailViolation] = []
    if isinstance(value, dict):
        for key, item in value.items():
            violations.extend(check_json_value(item, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            violations.extend(check_json_value(item, path=f"{path}[{i}]"))
    elif isinstance(value, str) and value.strip():
        for pattern in INJECTION_PATTERNS[:4]:
            if pattern.search(value) and len(value) < 500:
                violations.append(
                    GuardrailViolation(
                        code="json_injection",
                        message=f"Unsafe content in model JSON at {path}.",
                        severity="block",
                    )
                )
                break
        for name, pattern in PII_PATTERNS:
            if pattern.search(value):
                violations.append(
                    GuardrailViolation(
                        code=f"json_pii_{name}",
                        message=f"PII detected in model JSON at {path}.",
                        severity="block",
                    )
                )
    return violations
