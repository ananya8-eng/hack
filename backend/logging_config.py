"""
Central logging setup: pipeline/agent logs at INFO, noisy HTTP/access logs suppressed.
"""
from __future__ import annotations

import logging
import re

# Loggers that carry LangGraph, LLM, RAG, chunking, scraping, validation, etc.
_PIPELINE_LOGGER_PREFIXES = (
    "backend.",
    "backend.agents",
    "backend.graph",
    "backend.rag",
    "backend.tools",
    "backend.ingestion",
    "backend.extraction",
)

_STATUS_POLL_PATTERN = re.compile(
    r'GET /api/reports/[0-9a-f-]{36}/status HTTP'
)


class _SuppressStatusPollAccessFilter(logging.Filter):
    """Drop uvicorn access lines for high-frequency report status polling."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if _STATUS_POLL_PATTERN.search(message):
            return False
        return True


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(level)

    for name in _PIPELINE_LOGGER_PREFIXES:
        logging.getLogger(name).setLevel(level)

    access_logger = logging.getLogger("uvicorn.access")
    status_filter = _SuppressStatusPollAccessFilter()
    if not any(isinstance(f, _SuppressStatusPollAccessFilter) for f in access_logger.filters):
        access_logger.addFilter(status_filter)
    for handler in access_logger.handlers:
        if not any(isinstance(f, _SuppressStatusPollAccessFilter) for f in handler.filters):
            handler.addFilter(status_filter)

    for noisy in (
        "httpx",
        "httpcore",
        "huggingface_hub",
        "sentence_transformers",
        "transformers",
        "watchfiles",
        "qdrant_client",
        "urllib3",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)
