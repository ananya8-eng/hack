import logging
from typing import List, Type

logger = logging.getLogger(__name__)


def _load_recursive_splitter() -> Type:
    """LangChain >=0.2 exposes splitters in langchain-text-splitters."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        return RecursiveCharacterTextSplitter
    except ImportError:
        pass
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        return RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise ImportError(
            "Install langchain-text-splitters: pip install langchain-text-splitters"
        ) from exc


def _fallback_chunk(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    chunks: List[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
        if start >= text_len or chunk_size <= chunk_overlap:
            break
    return chunks


def split_text_into_chunks(text: str, chunk_size: int = 700, chunk_overlap: int = 100) -> list:
    """
    Split text with LangChain RecursiveCharacterTextSplitter (paragraph/sentence aware).
    """
    if not text:
        return []

    try:
        splitter_cls = _load_recursive_splitter()
        splitter = splitter_cls(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_text(text)
        if chunks:
            return chunks
    except ImportError:
        logger.warning(
            "langchain-text-splitters not installed. Using simple fallback chunker. "
            "Run: pip install langchain-text-splitters"
        )
    except Exception as exc:
        logger.warning("LangChain chunking failed (%s). Using simple fallback chunker.", exc)

    return _fallback_chunk(text, chunk_size, chunk_overlap)
