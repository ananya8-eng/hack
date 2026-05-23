import logging
import re
import uuid

logger = logging.getLogger(__name__)

def split_text_into_chunks(text: str, chunk_size: int = 700, chunk_overlap: int = 100) -> list:
    """
    Splits text into chunks of specified size and overlap.
    Uses LangChain's RecursiveCharacterTextSplitter with a custom fallback.
    """
    if not text:
        return []
        
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = splitter.split_text(text)
        return chunks
    except ImportError:
        logger.warning("langchain text splitter is not installed. Using simple fallback chunker.")
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(text[start:end])
            start += chunk_size - chunk_overlap
            if start >= text_len or chunk_size <= chunk_overlap:
                break
        return chunks


def build_section_chunks(
    text: str,
    base_metadata: dict,
    child_size: int = 700,
    child_overlap: int = 100,
    parent_size: int = 1400,
    parent_overlap: int = 150,
) -> list:
    """
    Builds section-scoped child chunks with parent chunk references and useful
    trace metadata. Call this once per extracted filing section so chunks never
    cross section boundaries.
    """
    if not text:
        return []

    records = []
    parent_chunks = _chunk_with_ranges(text, parent_size, parent_overlap)
    seen_overlap_sentences = set()

    for parent_index, parent in enumerate(parent_chunks):
        parent_chunk_id = (
            f"{base_metadata.get('report_id', 'report')}_"
            f"{base_metadata.get('section', 'section')}_parent_{parent_index}_{uuid.uuid4().hex[:6]}"
        )
        child_chunks = _chunk_with_ranges(parent["text"], child_size, child_overlap, offset=parent["char_start"])

        for child_index, child in enumerate(child_chunks):
            duplicate_count = _count_duplicate_sentences(child["text"], seen_overlap_sentences)
            metadata = {
                **base_metadata,
                "chunk_index": len(records),
                "parent_chunk_id": parent_chunk_id,
                "parent_chunk_index": parent_index,
                "child_chunk_index": child_index,
                "char_start": child["char_start"],
                "char_end": child["char_end"],
                "parent_char_start": parent["char_start"],
                "parent_char_end": parent["char_end"],
                "duplicate_sentence_count": duplicate_count,
                "chunking_strategy": "section_parent_child"
            }
            records.append({
                "text": child["text"],
                "metadata": metadata
            })

    return records


def _chunk_with_ranges(text: str, chunk_size: int, chunk_overlap: int, offset: int = 0) -> list:
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end), text.rfind(" ", start, end))
            if boundary > start + int(chunk_size * 0.6):
                end = boundary + (1 if text[boundary] == "\n" else 0)

        chunk_text = text[start:end].strip()
        if chunk_text:
            leading_trim = len(text[start:end]) - len(text[start:end].lstrip())
            trailing_trim = len(text[start:end]) - len(text[start:end].rstrip())
            chunks.append({
                "text": chunk_text,
                "char_start": offset + start + leading_trim,
                "char_end": offset + end - trailing_trim
            })

        if end >= text_len or chunk_size <= chunk_overlap:
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def _count_duplicate_sentences(text: str, seen_sentences: set) -> int:
    sentences = [
        sentence.strip().lower()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if len(sentence.strip()) > 30
    ]
    duplicate_count = sum(1 for sentence in sentences if sentence in seen_sentences)
    seen_sentences.update(sentences)
    return duplicate_count
