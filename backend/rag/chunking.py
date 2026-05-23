import logging

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
        # Fallback manual chunker
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
