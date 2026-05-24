"""Guardrail result types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass(frozen=True)
class GuardrailViolation:
    code: str
    message: str
    severity: str = "block"  # block | warn


@dataclass
class GuardrailResult:
    allowed: bool
    violations: List[GuardrailViolation] = field(default_factory=list)
    sanitized_text: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, text: str | None = None, **metadata: Any) -> "GuardrailResult":
        return cls(allowed=True, sanitized_text=text, metadata=dict(metadata))

    @classmethod
    def blocked(cls, violations: List[GuardrailViolation], **metadata: Any) -> "GuardrailResult":
        return cls(allowed=False, violations=violations, metadata=dict(metadata))

    def user_message(self) -> str:
        if not self.violations:
            return "Request blocked by safety policy."
        return " ".join(v.message for v in self.violations[:3])

    def to_api_payload(self) -> dict[str, Any]:
        return {
            "success": False,
            "guardrail_blocked": True,
            "violations": [
                {"code": v.code, "message": v.message, "severity": v.severity}
                for v in self.violations
            ],
            "answer": self.user_message(),
            "citations": [],
        }
