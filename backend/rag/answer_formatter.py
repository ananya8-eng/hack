from typing import Dict, Any, List

def format_rag_response(
    answer: str,
    verified_citations: List[Dict],
    unverified_claims: List[Dict],
    guard_result: Dict[str, Any],
    query_route: Dict[str, Any],
    retrieval_stats: Dict[str, Any],
    session_id: str = None
) -> Dict[str, Any]:
    """
    Assembles the final structured RAG response payload, rich with metadata
    for the frontend dashboard.
    """
    
    # If the hallucination guard flagged critical issues, we can append a disclaimer
    # or alter the answer. Here we just add a disclaimer if confidence is low.
    final_answer = answer
    confidence = guard_result.get("confidence", 1.0)
    
    if confidence < 0.7:
        disclaimer = "\n\n*(Disclaimer: The system detected potential inconsistencies in this answer. Please verify against the cited sources.)*"
        final_answer += disclaimer
        
    response = {
        "answer": final_answer,
        "citations": verified_citations,
        "confidence_score": confidence,
        "is_safe": guard_result.get("is_safe", True),
        "flags": guard_result.get("flags", []),
        "unverified_claims": unverified_claims,
        "query_type": query_route.get("query_type", "unknown"),
        "retrieval_metadata": retrieval_stats,
        "success": True
    }
    
    if session_id:
        response["session_id"] = session_id
        
    return response
