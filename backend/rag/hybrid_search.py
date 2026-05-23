import logging
import math
from typing import List, Dict

logger = logging.getLogger(__name__)

class HybridSearchEngine:
    """
    Implements Hybrid Search (Vector + Keyword) using Reciprocal Rank Fusion (RRF).
    """
    
    def __init__(self, vector_store_manager):
        # Passed in chroma_tool manager
        self.vsm = vector_store_manager

    def search(
        self, 
        query: str, 
        report_id: str = None, 
        n_results: int = 20, 
        where: dict = None,
        alpha: float = 0.5  # 1.0 = purely semantic, 0.0 = purely keyword
    ) -> List[Dict]:
        """
        Perform hybrid search.
        Since ChromaDB doesn't natively support BM25 natively without specific plugins,
        we retrieve more from vector search and use rank_bm25 locally if available,
        or just do vector search if alpha=1.0.
        """
        # Get semantic results
        semantic_results = self.vsm.query_similar_chunks(
            query_text=query,
            n_results=n_results,
            where=where,
            report_id=report_id
        )

        if alpha >= 1.0 or not semantic_results:
            return semantic_results

        # Attempt Keyword search (BM25) re-ranking on the semantic subset or full set
        # For a true hybrid search, we would search an inverted index here. 
        # Since we're bridging this over Chroma, we use BM25 to re-rank the retrieved semantic window.
        try:
            from rank_bm25 import BM25Okapi
            
            tokenized_corpus = [doc["document"].lower().split() for doc in semantic_results]
            bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = query.lower().split()
            bm25_scores = bm25.get_scores(tokenized_query)
            
            # Reciprocal Rank Fusion (RRF)
            # RRF Score = 1 / (k + rank)
            k = 60
            
            # Rank semantic results
            for i, doc in enumerate(semantic_results):
                doc["semantic_rank"] = i + 1
            
            # Rank BM25 results
            bm25_ranked_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
            for rank, idx in enumerate(bm25_ranked_indices):
                semantic_results[idx]["keyword_rank"] = rank + 1
                
            # Fuse
            for doc in semantic_results:
                rrf_semantic = 1.0 / (k + doc["semantic_rank"])
                rrf_keyword = 1.0 / (k + doc["keyword_rank"])
                doc["hybrid_score"] = (alpha * rrf_semantic) + ((1.0 - alpha) * rrf_keyword)
                
            # Re-sort by hybrid score
            semantic_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
            logger.info("Hybrid Search (Vector + BM25) completed using RRF.")
            return semantic_results

        except ImportError:
            logger.debug("rank_bm25 not installed. Returning semantic-only search.")
            return semantic_results
        except Exception as e:
            logger.warning(f"Hybrid search BM25 error: {e}. Returning semantic results.")
            return semantic_results

    def filter_mmr(self, query: str, results: List[Dict], top_k: int = 5, diversity: float = 0.3) -> List[Dict]:
        """
        Maximal Marginal Relevance (MMR)
        Selects documents that are relevant to the query but diverse from each other.
        We approximate this by penalizing subsequent documents that have high term overlap 
        with already selected documents.
        """
        if not results or len(results) <= top_k:
            return results

        selected = [results[0]]
        remaining = results[1:]

        while len(selected) < top_k and remaining:
            best_idx = 0
            best_score = -float("inf")
            
            for i, doc in enumerate(remaining):
                # Relevance (we use its existing rerank or hybrid score, assuming max=1.0 approx)
                rel_score = doc.get("rerank_score", doc.get("hybrid_score", doc.get("score", 0.5)))
                
                # Similarity to already selected docs (simple term overlap penalty)
                doc_terms = set(doc["document"].lower().split())
                max_sim = 0
                for sel_doc in selected:
                    sel_terms = set(sel_doc["document"].lower().split())
                    if sel_terms:
                        overlap = len(doc_terms.intersection(sel_terms)) / len(sel_terms)
                        max_sim = max(max_sim, overlap)
                
                # MMR Equation
                mmr_score = (1.0 - diversity) * rel_score - (diversity * max_sim)
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
                    
            selected.append(remaining.pop(best_idx))

        return selected

