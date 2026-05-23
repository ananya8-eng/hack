import re
import logging

logger = logging.getLogger(__name__)

def extract_sections(text: str) -> dict:
    """
    Extracts key narrative sections (Risk Factors, MD&A, and Forward-Looking Statements)
    from the raw filing text using a series of regexes.
    """
    sections = {
        "risk_factors": "",
        "mda": "",
        "forward_looking": ""
    }
    
    if not text:
        return sections

    # Normalize whitespace for easier regex matching
    normalized_text = re.sub(r'\s+', ' ', text)
    
    # 1. RISK FACTORS (Item 1A)
    # SEC filings usually use "Item 1A. Risk Factors" or similar.
    # We search from Item 1A to Item 1B (Unresolved Staff Comments) or Item 2 (Properties).
    risk_patterns = [
        r"(?i)ITEM\s+1A\.?\s+Risk\s+Factors(.*?)(?:ITEM\s+1B|ITEM\s+2\.)",
        r"(?i)ITEM\s+1A\.?\s+Risk\s+Factors(.*?)(?:ITEM\s+1B|ITEM\s+2)",
        r"(?i)Risk\s+Factors(.*?)(?:Item\s+1B|Item\s+2|Management\'s\s+Discussion)",
        r"(?i)ITEM\s+1A\.?\s*(.*?)(?:ITEM\s+1B|ITEM\s+2)"
    ]
    
    for pattern in risk_patterns:
        match = re.search(pattern, normalized_text, re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            # If the extraction is too small, it's likely a false match (e.g. table of contents link)
            if len(extracted) > 500:
                sections["risk_factors"] = extracted
                break
                
    # 2. MANAGEMENT'S DISCUSSION AND ANALYSIS (MD&A - Item 7)
    # We search from Item 7 to Item 7A (Quantitative and Qualitative Disclosures About Market Risk) or Item 8 (Financial Statements).
    mda_patterns = [
        r"(?i)ITEM\s+7\.?\s+Management\'s\s+Discussion\s+and\s+Analysis\s+of\s+Financial\s+Condition(.*?)(?:ITEM\s+7A|ITEM\s+8\.)",
        r"(?i)ITEM\s+7\.?\s+Management\'s\s+Discussion(.*?)(?:ITEM\s+7A|ITEM\s+8)",
        r"(?i)Management\'s\s+Discussion\s+and\s+Analysis(.*?)(?:Item\s+7A|Item\s+8)",
        r"(?i)ITEM\s+7\.?\s*(.*?)(?:ITEM\s+7A|ITEM\s+8)"
    ]
    
    for pattern in mda_patterns:
        match = re.search(pattern, normalized_text, re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if len(extracted) > 500:
                sections["mda"] = extracted
                break

    # 3. FORWARD LOOKING STATEMENTS
    # Typically a standard paragraph/section under a heading near the beginning of the filing.
    fls_patterns = [
        r"(?i)(?:forward[- ]looking\s+statements|cautionary\s+statement\s+regarding\s+forward[- ]looking\s+statements)(.*?)(?:Item\s+1|PART\s+I)",
        r"(?i)(?:forward[- ]looking\s+statements|cautionary\s+note|forward[- ]looking\s+information)(.{500,3000}?)(?:\n\n|\r\n\r\n|ITEM)"
    ]
    
    for pattern in fls_patterns:
        match = re.search(pattern, normalized_text, re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if len(extracted) > 200:
                sections["forward_looking"] = extracted
                break

    # Robust Fallbacks if any section is empty, to ensure the UI has plenty of data to display
    if not sections["risk_factors"]:
        # Look for general occurrences of "risk" or partition a section of the text
        logger.warning("Standard Risk Factors heading not found. Using text-heuristic fallback.")
        # Find paragraphs containing "risk" or "severity"
        risk_sentences = [s for s in text.split('\n') if any(w in s.lower() for w in ['risk', 'uncertainty', 'adversely affect', 'competition'])]
        sections["risk_factors"] = "\n".join(risk_sentences[:50]) or "No explicit Risk Factors section could be isolated, but risk factors are integrated within the document."

    if not sections["mda"]:
        logger.warning("Standard MD&A heading not found. Using text-heuristic fallback.")
        mda_sentences = [s for s in text.split('\n') if any(w in s.lower() for w in ['liquidity', 'revenue', 'capital resources', 'operations', 'financial condition'])]
        sections["mda"] = "\n".join(mda_sentences[:50]) or "No explicit MD&A section could be isolated, but management discussion details are found throughout the document."

    if not sections["forward_looking"]:
        fls_sentences = [s for s in text.split('\n') if any(w in s.lower() for w in ['forward-looking', 'expect', 'anticipate', 'project', 'intend', 'will'])]
        sections["forward_looking"] = "\n".join(fls_sentences[:15]) or "Standard Forward-Looking Statements warnings are in effect for all forward projections in this filing."

    return sections
