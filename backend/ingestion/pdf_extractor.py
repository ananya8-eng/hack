import logging
import os
from typing import List, Tuple

logger = logging.getLogger(__name__)


def extract_pdf_text(pdf_path_or_bytes) -> str:
    """
    Extract all text from a PDF with page markers for section discovery on large filings.
    """
    pages = extract_pdf_pages(pdf_path_or_bytes)
    if not pages:
        return ""
    parts: List[str] = []
    for page_num, page_text in pages:
        cleaned = (page_text or "").strip()
        if cleaned:
            parts.append(f"--- PAGE {page_num} ---\n{cleaned}")
    return "\n\n".join(parts)


def extract_pdf_pages(pdf_path_or_bytes) -> List[Tuple[int, str]]:
    """
    Returns [(page_number_1based, text), ...] for the full document.
    """
    pages: List[Tuple[int, str]] = []
    try:
        import fitz  # PyMuPDF

        if isinstance(pdf_path_or_bytes, str):
            if not os.path.exists(pdf_path_or_bytes):
                raise FileNotFoundError(f"PDF file not found at: {pdf_path_or_bytes}")
            doc = fitz.open(pdf_path_or_bytes)
        else:
            doc = fitz.open(stream=pdf_path_or_bytes, filetype="pdf")

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text() or ""
            pages.append((page_num + 1, page_text))
        doc.close()
        logger.info("Extracted %s pages from PDF", len(pages))

    except ImportError:
        logger.warning("PyMuPDF (fitz) is not installed. Using degraded PDF parsing.")
        if isinstance(pdf_path_or_bytes, bytes):
            raw = pdf_path_or_bytes.decode("utf-8", errors="ignore")
        else:
            with open(pdf_path_or_bytes, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        if raw.strip():
            pages = [(1, raw)]
    except Exception as e:
        logger.error("Error extracting PDF text: %s", e)
        raise RuntimeError(f"Failed to extract PDF text: {e}") from e

    return pages
