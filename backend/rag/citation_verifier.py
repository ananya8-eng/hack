import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class CitationVerifier:
    """
    Post-generation audit of citations.
    Ensures that every citation claimed by the LLM maps to a retrieved chunk,
    and performs basic overlap checks to verify the claim isn't entirely hallucinated.
    """
    
    def verify_citations(self, answer: str, retrieved_chunks: List[Dict]) -> Dict[str, Any]:
        """
        Parses `[Citation ID]` from the answer and verifies them against source chunks.
        Returns the verified answer, a list of verified citations, and any unverified claims.
        """
        if not answer:
            return {"verified_answer": "", "verified_citations": [], "unverified_claims": []}
            
        # Parse all citations in the format [Company Section - Chunk N]
        # We allow slight variations in spacing
        citation_pattern = r"\[([^\]]+)\]"
        matches = list(re.finditer(citation_pattern, answer))
        
        verified_citations = []
        unverified_claims = []
        
        # Build a lookup map of retrieved chunks by a synthesized ID format
        chunk_map = {}
        for i, item in enumerate(retrieved_chunks):
            meta = item.get("metadata", {})
            sec = meta.get("section", "Section").replace("_", " ").title()
            comp = meta.get("company", "Company")
            chunk_idx = meta.get("chunk_index", i)
            citation_id = f"{comp} {sec} - Chunk {chunk_idx}"
            chunk_map[citation_id.lower()] = {
                "citation_id": f"[{citation_id}]",
                "section": sec,
                "company": comp,
                "chunk_index": chunk_idx,
                "content": item.get('document', '')
            }

        # Validate each match
        for match in matches:
            raw_citation = match.group(1).strip()
            
            # Simple heuristic: if it doesn't look like our citation format, ignore it
            if "Chunk" not in raw_citation:
                continue
                
            # Check if this cited ID exists in our retrieved chunks
            citation_key = raw_citation.lower()
            if citation_key in chunk_map:
                # Get the sentence preceding the citation to verify overlap
                # This is a basic heuristic verification
                end_pos = match.start()
                start_pos = max(0, answer.rfind(".", 0, end_pos))
                claim_sentence = answer[start_pos:end_pos].strip(" .")
                
                source_content = chunk_map[citation_key]["content"].lower()
                
                # Check for word overlap (excluding stop words)
                claim_words = set(w.lower() for w in claim_sentence.split() if len(w) > 4)
                if claim_words:
                    overlap = sum(1 for w in claim_words if w in source_content)
                    overlap_ratio = overlap / len(claim_words)
                    
                    if overlap_ratio < 0.1:
                        # Very low overlap, might be hallucinated or heavily paraphrased
                        logger.warning(f"Low overlap for citation [{raw_citation}]. Claim: '{claim_sentence}'")
                        unverified_claims.append({
                            "claim": claim_sentence,
                            "cited_source": raw_citation,
                            "reason": "Low lexical overlap with source chunk"
                        })
                
                # Add to verified citations if not already there
                if chunk_map[citation_key] not in verified_citations:
                    verified_citations.append(chunk_map[citation_key])
            else:
                # The LLM hallucinated a citation ID that we didn't retrieve!
                logger.warning(f"Hallucinated citation detected: [{raw_citation}]")
                # We could actively remove the fake citation from the answer text here
                
                # Find the claim
                end_pos = match.start()
                start_pos = max(0, answer.rfind(".", 0, end_pos))
                claim_sentence = answer[start_pos:end_pos].strip(" .")
                
                unverified_claims.append({
                    "claim": claim_sentence,
                    "cited_source": raw_citation,
                    "reason": "Cited chunk was not in the retrieved context"
                })

        return {
            "verified_answer": answer,
            "verified_citations": verified_citations,
            "unverified_claims": unverified_claims
        }

# Singleton
citation_verifier = CitationVerifier()
