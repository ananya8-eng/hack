"""Central guardrails engine for API and LLM calls."""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from backend.config import get_settings
from backend.guardrails.checks import (
    Channel,
    check_json_value,
    check_text,
    sanitize_llm_output,
)
from backend.guardrails.policies import (
    DEFAULT_MAX_CHAT_INPUT_CHARS,
    DEFAULT_MAX_LLM_OUTPUT_CHARS,
    DEFAULT_MAX_PROMPT_CHARS,
    DEFAULT_MAX_UPLOAD_QUERY_CHARS,
    SYSTEM_POLICY_PREFIX,
)
from backend.guardrails.types import GuardrailResult, GuardrailViolation

logger = logging.getLogger(__name__)


class GuardrailsEngine:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.guardrails_enabled
        self.max_chat_chars = settings.guardrails_max_chat_chars
        self.max_upload_query_chars = settings.guardrails_max_upload_query_chars
        self.max_prompt_chars = settings.guardrails_max_prompt_chars
        self.max_output_chars = settings.guardrails_max_llm_output_chars
        self.require_financial_scope = settings.guardrails_require_financial_scope

    def check_chat_message(self, message: str) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult.ok((message or "").strip())
        return check_text(
            message,
            channel="chat",
            max_chars=self.max_chat_chars,
            require_financial_scope=self.require_financial_scope,
        )

    def check_upload_query(self, query: str) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult.ok((query or "").strip())
        if not (query or "").strip():
            return GuardrailResult.ok("")
        return check_text(
            query,
            channel="upload_query",
            max_chars=self.max_upload_query_chars,
            require_financial_scope=self.require_financial_scope,
        )

    def prepare_llm_prompt(self, prompt: str) -> GuardrailResult:
        """Validate prompt size and injection; return wrapped prompt for providers."""
        if not self.enabled:
            return GuardrailResult.ok(prompt)

        stripped = (prompt or "").strip()
        if len(stripped) > self.max_prompt_chars:
            return GuardrailResult.blocked(
                [
                    GuardrailViolation(
                        code="prompt_too_long",
                        message="Internal prompt exceeds allowed size.",
                        severity="block",
                    )
                ]
            )

        injection = check_text(
            self._extract_user_directive(stripped),
            channel="llm_prompt",
            max_chars=self.max_prompt_chars,
            require_financial_scope=False,
        )
        if not injection.allowed:
            return injection

        if SYSTEM_POLICY_PREFIX in stripped:
            wrapped = stripped
        else:
            wrapped = f"{SYSTEM_POLICY_PREFIX}\n\n{stripped}"

        return GuardrailResult.ok(wrapped)

    def check_llm_text_output(self, text: str) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult.ok((text or "").strip())
        return sanitize_llm_output(text, max_chars=self.max_output_chars)

    def check_llm_json_output(self, payload: dict[str, Any]) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult.ok(metadata={"json": payload})
        violations = check_json_value(payload)
        if violations:
            logger.warning(
                "Guardrails blocked JSON output: %s",
                [v.code for v in violations],
            )
            return GuardrailResult.blocked(violations)
        return GuardrailResult.ok(metadata={"json": payload})

    @staticmethod
    def _extract_user_directive(prompt: str) -> str:
        """
        Scan likely user-controlled tail of composite prompts (questions / tasks).
        Reduces false positives from filing boilerplate mentioning 'system' etc.
        """
        markers = (
            "[User Question]",
            "[User comparison question]",
            "[Task]",
            "Query:",
        )
        for marker in markers:
            idx = prompt.rfind(marker)
            if idx >= 0:
                return prompt[idx:]
        tail = prompt[-4000:] if len(prompt) > 4000 else prompt
        return tail


guardrails = GuardrailsEngine()
