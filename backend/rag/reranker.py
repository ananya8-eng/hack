import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class ReRanker:
    """
    Cross-encoder based re-ranker to improve retrieval quality.
    Takes a query and a list of candidate chunks, and re-scores them.
    If the cross-encoder model is not available, uses a heuristic fallback.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ReRanker, cls).__new__(cls)
            cls._instance.model = None
            cls._instance.initialized = False
            cls._instance.use_fallback = False
        return cls._instance

    def initialize(self):
        if self.initialized:
            return

        mode = os.environ.get("RERANKER_MODE", "fallback").lower()
        if mode == "fallback":
            logger.info("ReRanker mode: FALLBACK (Heuristic scoring)")
            self.use_fallback = True
            self.initialized = True
            return

        try:
            from sentence_transformers import CrossEncoder
            model_name = os.environ.get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.info(f"Loading CrossEncoder re-ranker '{model_name}'...")
            self.model = CrossEncoder(model_name)
            logger.info(f"CrossEncoder '{model_name}' loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load CrossEncoder: {str(e)}. Using fallback reranker.")
            self.use_fallback = True
            
        self.initialized = True

    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Re-rank a list of candidate chunk dictionaries.
        Expected format of candidates: [{"document": "...", "metadata": {...}, "id": "..."}, ...]
        Returns the top_k re-ranked candidates with updated 'score' fields.
        """
        if not candidates:
            return []

        if not self.initialized:
            self.initialize()

        if self.use_fallback or self.model is None:
            return self._fallback_rerank(query, candidates, top_k)

        try:
            # Pair query with each candidate document
            pairs = [[query, doc["document"]] for doc in candidates]
            scores = self.model.predict(pairs)
            
            # Attach scores to candidates
            for i, score in enumerate(scores):
                candidates[i]["rerank_score"] = float(score)
            
            # Sort descending by score
            candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            return candidates[:top_k]
            
        except Exception as e:
            logger.error(f"Error during cross-encoder reranking: {e}. Falling back.")
            return self._fallback_rerank(query, candidates, top_k)

    def _fallback_rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Simple heuristic fallback re-ranker based on term frequency overlap.
        Useful when models are not downloaded.
        """
        query_terms = set(w.lower() for w in query.replace("?", "").replace(".", "").split() if len(w) > 3)
        
        for doc in candidates:
            text = doc["document"].lower()
            overlap_score = sum(1 for term in query_terms if term in text)
            # Combine initial vector score with overlap score
            initial_score = doc.get("score", 0.0)
            doc["rerank_score"] = initial_score + (overlap_score * 0.1)
            
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates[:top_k]

# Singleton helper
reranker = ReRanker()
