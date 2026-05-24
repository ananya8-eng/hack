"""Data models for PDF-specific narrative sections."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class FilingSection:
    """One narrative block discovered in a specific filing (not a fixed schema)."""

    id: str
    title: str
    text: str
    priority: int
    source: str  # item_heading | llm_outline | fallback_chunk

    def to_catalog_entry(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "char_count": len(self.text),
            "priority": self.priority,
            "source": self.source,
        }


def sections_to_text_map(sections: List[FilingSection]) -> Dict[str, str]:
    return {s.id: s.text for s in sections}


def sections_catalog(sections: List[FilingSection]) -> List[Dict[str, Any]]:
    return [s.to_catalog_entry() for s in sections]
