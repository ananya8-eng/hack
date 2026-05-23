import logging
from typing import Dict, Any

from backend.tools.chroma_tool import chromadb_manager
from backend.tools.embedding_tool import embedding_manager
from backend.rag.hybrid_search import HybridSearchEngine
from backend.rag.reranker import reranker
from backend.rag.query_router import query_router

logger = logging.getLogger(__name__)

def get_diagnostics(report_id: str, company: str) -> Dict[str, Any]:
    """
    Gathers diagnostic information about the RAG system for a specific report.
    This helps in debugging retrieval quality and system health.
    """
    diagnostics = {
        "report_id": report_id,
        "company": company,
        "system_status": {},
        "collection_stats": {},
        "sample_retrieval": {}
    }
    if not reranker.initialized:
        reranker.initialize()
    
    # 1. System Status
    diagnostics["system_status"] = {
        "embedding_mode": "real" if embedding_manager.is_using_real_model else "mock",
        "embedding_dim": embedding_manager.embedding_dim,
        "reranker_active": not reranker.use_fallback,
        "chroma_persistent": not chromadb_manager.use_fallback
    }
    
    # 2. Collection Stats
    stats = chromadb_manager.get_collection_stats(report_id)
    diagnostics["collection_stats"] = stats
    
    # 3. Sample Retrieval Test
    if stats.get("total_chunks", 0) > 0:
        sample_query = f"What are the main risks for {company}?"
        
        # Route
        route = query_router.classify_query(sample_query)
        
        # Hybrid Search
        search_engine = HybridSearchEngine(chromadb_manager)
        chunks = search_engine.search(
            query=sample_query,
            report_id=report_id,
            n_results=5,
            alpha=route["alpha"]
        )
        
        # Rerank
        if chunks:
            reranked = reranker.rerank(sample_query, chunks, top_k=3)
            mmr_filtered = search_engine.filter_mmr(sample_query, reranked, top_k=2)
            
            diagnostics["sample_retrieval"] = {
                "query": sample_query,
                "route": route,
                "chunks_found": len(chunks),
                "top_result_preview": mmr_filtered[0]["document"][:150] + "..." if mmr_filtered else None,
                "top_result_score": mmr_filtered[0].get("rerank_score") if mmr_filtered else None
            }
        else:
            diagnostics["sample_retrieval"] = {"error": "No chunks retrieved"}
            
    return diagnostics
