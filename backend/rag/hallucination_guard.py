import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class HallucinationGuard:
    """
    Evaluates the RAG answer for hallucinations, numerical discrepancies,
    and assigns a confidence score. Can trigger fallbacks.
    """
    
    def check_faithfulness(self, answer: str, chunks: List[Dict]) -> Dict[str, Any]:
        """
        Heuristic faithfulness check.
        1. Verifies that all numbers/percentages mentioned in the answer exist in the source chunks.
        2. Assigns a confidence score.
        """
        if not answer or not chunks:
            return {"confidence": 0.0, "is_safe": False, "flags": ["No answer or chunks"]}
            
        flags = []
        is_safe = True
        confidence = 1.0
        
        source_text = " ".join([c.get("document", "") for c in chunks])
        source_companies = " ".join([
            str(c.get("metadata", {}).get("company", "")) for c in chunks
        ])
        source_lower = source_text.lower()
        source_identity_lower = f"{source_text} {source_companies}".lower()
        answer_without_citations = re.sub(r"\[[^\]]+\]", "", answer)
        
        # 1. Check if LLM explicitly stated it couldn't find the answer
        if "cannot find sufficient evidence" in answer.lower():
            return {
                "confidence": 1.0, 
                "is_safe": True, 
                "flags": ["Correctly declined to answer (insufficient context)"]
            }
            
        # 2. Number verification (strict)
        # Find all numbers/percentages in the answer
        number_pattern = r"\b\d+(?:\.\d+)?%?\b"
        answer_numbers = re.findall(number_pattern, answer_without_citations)
        
        source_numbers = set(re.findall(number_pattern, source_text))
        
        unsupported_numbers = []
        for num in answer_numbers:
            # Simple matching: the exact number string must appear in the source
            # E.g., if answer says "15%", "15%" must be in the source.
            if num not in source_numbers:
                unsupported_numbers.append(num)
                
        if unsupported_numbers:
            flags.append(f"Contains unsupported numbers: {', '.join(unsupported_numbers[:5])}")
            confidence -= 0.3
            is_safe = False
            
        # 3. Company name verification
        # If the answer mentions major companies, verify they are in the source
        major_companies = ["NVIDIA", "AMD", "Intel", "TSMC", "Apple", "Microsoft", "Google"]
        for comp in major_companies:
            if comp in answer_without_citations and comp.lower() not in source_identity_lower:
                flags.append(f"Mentions '{comp}' but it's not in the retrieved context.")
                confidence -= 0.2
                is_safe = False

        # Normalize confidence
        confidence = max(0.0, min(1.0, confidence))
        
        if not is_safe:
            logger.warning(f"Hallucination Guard flagged response. Confidence: {confidence}. Flags: {flags}")

        return {
            "confidence": round(confidence, 2),
            "is_safe": is_safe,
            "flags": flags
        }

# Singleton
hallucination_guard = HallucinationGuard()
