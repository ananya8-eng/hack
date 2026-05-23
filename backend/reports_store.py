"""In-memory report store and live progress updates for polling UI."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

REPORTS_DB: Dict[str, Dict[str, Any]] = {}


def append_report_log(
    report_id: str,
    message: str,
    *,
    step: Optional[str] = None,
    status: Optional[str] = None,
) -> None:
    report = REPORTS_DB.get(report_id)
    if not report:
        return
    logs: List[str] = list(report.get("logs", []))
    logs.append(message)
    report["logs"] = logs
    if step:
        report["current_step"] = step
    if status:
        report["status"] = status
    elif report.get("status") == "queued":
        report["status"] = "processing"
