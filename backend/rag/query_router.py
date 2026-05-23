import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class QueryRouter:
    """
    Classifies queries into types to determine optimal search parameters.
    """
    
    @staticmethod
    def classify_query(query: str) -> Dict[str, Any]:
        """
        Determine query type to adjust alpha (hybrid search blend) and top_k.
        Types:
          - factual: specific numbers, dates, people (favors keyword search)
          - analytical: "why", "how", risk impact (favors semantic search)
          - comparative: "compare", "vs" (broad retrieval)
        """
        query_lower = query.lower()
        
        factual_patterns = [
            r"\bwhat is\b", r"\bhow much\b", r"\bwho\b", r"\bwhen\b", r"\bgross margin\b",
            r"\brevenue\b", r"\bpercent\b", r"%"
        ]
        
        analytical_patterns = [
            r"\bwhy\b", r"\bhow does\b", r"\bimpact\b", r"\baffect\b", r"\brisk\b", 
            r"\bstrategy\b", r"\bcause\b", r"\bexplain\b"
        ]
        
        comparative_patterns = [
            r"\bcompare\b", r"\bvs\b", r"\bversus\b", r"\bdifference\b", r"\bbetter\b", 
            r"\bworse\b"
        ]
        
        # Default fallback
        q_type = "analytical"
        alpha = 0.8  # Slight bias towards semantic
        
        if any(re.search(p, query_lower) for p in comparative_patterns):
            q_type = "comparative"
            alpha = 0.5  # Balanced
        elif any(re.search(p, query_lower) for p in analytical_patterns):
            q_type = "analytical"
            alpha = 0.9  # Heavy semantic
        elif any(re.search(p, query_lower) for p in factual_patterns):
            q_type = "factual"
            alpha = 0.3  # Heavy keyword
            
        logger.debug(f"QueryRouter classified '{query[:30]}...' as '{q_type}' (alpha={alpha})")
        
        return {
            "query_type": q_type,
            "alpha": alpha,
            "target_n_results": 20 if q_type == "comparative" else 15
        }

# Singleton
query_router = QueryRouter()
