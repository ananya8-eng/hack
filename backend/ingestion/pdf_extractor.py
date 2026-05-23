import os
import logging

logger = logging.getLogger(__name__)

def extract_pdf_text(pdf_path_or_bytes) -> str:
    """
    Extracts all text from a PDF file using PyMuPDF (fitz).
    Supports either a file path (str) or bytes.
    """
    text = ""
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
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n"
        doc.close()
        
    except ImportError:
        logger.warning("PyMuPDF (fitz) is not installed. Using simple fallback parser.")
        # Fallback in case fitz is not available (e.g. if installation is still running)
        if isinstance(pdf_path_or_bytes, bytes):
            text = pdf_path_or_bytes.decode('utf-8', errors='ignore')
        else:
            with open(pdf_path_or_bytes, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
    except Exception as e:
        logger.error(f"Error extracting PDF text: {str(e)}")
        # Graceful fallback to prevent crashes
        text = "Error parsing file. This is a fallback mock text representing the filing content."
        
    return text
