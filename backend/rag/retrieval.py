import re
import json
import logging
import requests
from backend.tools.chroma_tool import chromadb_manager
from backend.rag.hybrid_search import HybridSearchEngine
from backend.rag.reranker import reranker
from backend.rag.query_router import query_router
from backend.rag.conversation_memory import conversation_store
from backend.rag.prompt_templates import build_prompt
from backend.rag.citation_verifier import citation_verifier
from backend.rag.hallucination_guard import hallucination_guard
from backend.rag.answer_formatter import format_rag_response

logger = logging.getLogger(__name__)

def generate_heuristic_rag_answer(query: str, chunks: list) -> dict:
    """
    Determistically synthesizes a citation-backed answer strictly using
    the provided RAG chunks. Prevents hallucinations.
    """
    query_lower = query.lower()
    citations = []
    evidence_sentences = []
    
    # 1. Map keywords from query to find relevant sentences in chunks
    keywords = [w.strip("?,.!") for w in query_lower.split() if len(w) > 4]
    
    for i, item in enumerate(chunks):
        doc = item.get("document", "")
        meta = item.get("metadata", {})
        sec = meta.get("section", "Filing Detail").replace("_", " ").title()
        comp = meta.get("company", "Filing Entity")
        chunk_idx = meta.get("chunk_index", i)
        
        # Split chunk into sentences
        sentences = re.split(r'(?<=[.!?])\s+', doc)
        matching_sentences = []
        
        for s in sentences:
            if any(k in s.lower() for k in keywords):
                matching_sentences.append(s.strip())
                
        if matching_sentences:
            citation_id = f"[{comp} {sec} - Chunk {chunk_idx}]"
            citations.append({
                "citation_id": citation_id,
                "section": sec,
                "company": comp,
                "chunk_index": chunk_idx,
                "content": doc[:300] + "..."
            })
            # Add top sentences as evidence
            evidence_sentences.append((matching_sentences[0], citation_id))

    # 2. Synthesize response based on evidence
    if not evidence_sentences:
        # If no specific keyword match, use summaries of top chunks
        if chunks:
            top_item = chunks[0]
            meta = top_item.get("metadata", {})
            sec = meta.get("section", "Filing").replace("_", " ").title()
            comp = meta.get("company", "Company")
            chunk_idx = meta.get("chunk_index", 0)
            
            citation_id = f"[{comp} {sec} - Chunk {chunk_idx}]"
            citations.append({
                "citation_id": citation_id,
                "section": sec,
                "company": comp,
                "chunk_index": chunk_idx,
                "content": top_item.get("document")[:300] + "..."
            })
            
            answer = (
                f"Based on the retrieved {sec} section of {comp}, the filing discusses general operational conditions. "
                f"Specifically: \"{top_item.get('document')[:250]}...\" {citation_id}."
            )
        else:
            answer = "I could not find any relevant filing chunks in the database to answer your specific question. Please ensure a filing PDF is uploaded and processed first."
    else:
        # Build answer using the matches
        answer_parts = []
        answer_parts.append(f"Regarding your query on '{query}', the processed filing context shows: ")
        
        # Compile up to 3 evidence points
        added_points = 0
        for sent, cit in evidence_sentences[:3]:
            answer_parts.append(f"- {sent} {cit}")
            added_points += 1
            
        answer = " ".join(answer_parts)
        if len(evidence_sentences) > 3:
            answer += f" Additional structural indicators are mentioned in other parts of the filing."

    return {
        "answer": answer,
        "citations": citations,
        "success": True
    }

class RAGChatbot:
    def __init__(self, ollama_url="http://localhost:11434/api/generate"):
        self.ollama_url = ollama_url
        self.model_name = "qwen2.5:3b-instruct"

    def _call_ollama(self, prompt: str) -> str:
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=12
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            return ""
        except Exception:
            return ""

    def _prepare_chat(self, user_question: str, company_name: str = None, report_id: str = None, session_id: str = None) -> dict:
        logger.info(f"RAG Chatbot processing question: '{user_question}'...")

        if session_id and report_id:
            search_query = conversation_store.contextualize_query(user_question, report_id, session_id)
        else:
            search_query = user_question

        route = query_router.classify_query(search_query)
        alpha = route["alpha"]
        n_results_initial = route["target_n_results"]

        search_engine = HybridSearchEngine(chromadb_manager)
        where_filter = None
        if company_name and route["query_type"] != "comparative":
            where_filter = {"company": company_name}

        chunks = search_engine.search(
            query=search_query,
            report_id=report_id,
            n_results=n_results_initial,
            where=where_filter,
            alpha=alpha
        )
        
        if not chunks and not report_id and route["query_type"] != "comparative":
            # Broaden search to global only when the caller did not request a report scope.
            chunks = search_engine.search(
                query=search_query,
                n_results=n_results_initial,
                where=where_filter,
                alpha=alpha
            )

        logger.info(f"Hybrid retrieval fetched {len(chunks)} chunks.")

        if chunks:
            chunks = reranker.rerank(search_query, chunks, top_k=8)
            chunks = search_engine.filter_mmr(search_query, chunks, top_k=4, diversity=0.25)

        logger.info(f"Reranking & MMR distilled to {len(chunks)} top chunks.")

        context_parts = []
        for i, item in enumerate(chunks):
            meta = item.get("metadata", {})
            sec = meta.get("section", "Section").replace("_", " ").title()
            comp = meta.get("company", "Company")
            chunk_idx = meta.get("chunk_index", i)
            
            context_parts.append(
                f"Source [{comp} {sec} - Chunk {chunk_idx}]:\n"
                f"{item.get('document')}\n"
            )

        context_text = "\n".join(context_parts)

        history_str = ""
        if session_id and report_id:
            history_str = conversation_store.format_history_for_prompt(report_id, session_id)
            conversation_store.add_message(report_id, session_id, "user", user_question)

        prompt = build_prompt(
            query_type=route["query_type"],
            context_text=context_text,
            user_question=user_question,
            conversation_history=history_str
        )

        return {
            "search_query": search_query,
            "route": route,
            "alpha": alpha,
            "n_results_initial": n_results_initial,
            "chunks": chunks,
            "prompt": prompt
        }

    def _format_llm_response(self, response_text: str, chunks: list, route: dict, n_results_initial: int, alpha: float, session_id: str = None) -> dict:
        verification = citation_verifier.verify_citations(response_text, chunks)
        guard_result = hallucination_guard.check_faithfulness(response_text, chunks)

        verified_citations = verification["verified_citations"]
        if not verified_citations and chunks:
            for item in chunks:
                meta = item.get("metadata", {})
                sec = meta.get("section", "Section").replace("_", " ").title()
                comp = meta.get("company", "Company")
                chunk_idx = meta.get("chunk_index", 0)
                verified_citations.append({
                    "citation_id": f"[{comp} {sec} - Chunk {chunk_idx}]",
                    "section": sec,
                    "company": comp,
                    "chunk_index": chunk_idx,
                    "content": item.get("document")[:300] + "..."
                })

        retrieval_stats = {
            "chunks_retrieved_initial": n_results_initial,
            "chunks_after_rerank": len(chunks),
            "alpha_used": alpha,
            "search_strategy": "hybrid",
            "mmr_applied": bool(chunks)
        }

        return format_rag_response(
            answer=response_text.strip(),
            verified_citations=verified_citations,
            unverified_claims=verification["unverified_claims"],
            guard_result=guard_result,
            query_route=route,
            retrieval_stats=retrieval_stats,
            session_id=session_id
        )

    def _format_fallback_response(self, search_query: str, chunks: list, route: dict, n_results_initial: int, alpha: float, session_id: str = None) -> dict:
        logger.info("Executing Heuristic RAG Q&A Engine...")
        fallback_res = generate_heuristic_rag_answer(search_query, chunks)
        fallback_guard = hallucination_guard.check_faithfulness(fallback_res["answer"], chunks)
        if not chunks:
            fallback_guard = {
                "confidence": 0.0,
                "is_safe": True,
                "flags": ["No retrieved chunks available"]
            }

        return {
            "answer": fallback_res["answer"],
            "citations": fallback_res.get("citations", []),
            "confidence_score": fallback_guard.get("confidence", 0.0),
            "is_safe": fallback_guard.get("is_safe", True),
            "flags": fallback_guard.get("flags", []),
            "unverified_claims": [],
            "query_type": route.get("query_type"),
            "retrieval_metadata": {
                "chunks_retrieved_initial": n_results_initial,
                "chunks_after_rerank": len(chunks),
                "alpha_used": alpha,
                "search_strategy": "hybrid",
                "mmr_applied": bool(chunks)
            },
            "success": True,
            "session_id": session_id
        }

    def query_chatbot(self, user_question: str, company_name: str = None, report_id: str = None, session_id: str = None) -> dict:
        """
        Retrieves top relevant chunks from ChromaDB and uses Qwen
        to answer with precise inline citations.
        """
        prepared = self._prepare_chat(user_question, company_name, report_id, session_id)
        chunks = prepared["chunks"]
        route = prepared["route"]
        n_results_initial = prepared["n_results_initial"]
        alpha = prepared["alpha"]

        response_text = self._call_ollama(prepared["prompt"])
        
        if response_text and len(response_text.strip()) > 50:
            if session_id and report_id:
                conversation_store.add_message(report_id, session_id, "assistant", response_text.strip())
            return self._format_llm_response(response_text, chunks, route, n_results_initial, alpha, session_id)

        fallback_res = self._format_fallback_response(
            prepared["search_query"],
            chunks,
            route,
            n_results_initial,
            alpha,
            session_id
        )
        if session_id and report_id:
            conversation_store.add_message(report_id, session_id, "assistant", fallback_res["answer"])
        return fallback_res

    def stream_chatbot(self, user_question: str, company_name: str = None, report_id: str = None, session_id: str = None):
        """
        Yields ("token", text) chunks from Ollama when available, followed by
        ("metadata", dict). Falls back to the deterministic answer path if the
        local model is offline.
        """
        prepared = self._prepare_chat(user_question, company_name, report_id, session_id)
        chunks = prepared["chunks"]
        route = prepared["route"]
        n_results_initial = prepared["n_results_initial"]
        alpha = prepared["alpha"]
        answer_parts = []

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model_name,
                    "prompt": prepared["prompt"],
                    "stream": True,
                    "options": {"temperature": 0.1}
                },
                stream=True,
                timeout=12
            )
            if response.status_code != 200:
                raise RuntimeError(f"Ollama returned {response.status_code}")

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                payload = json.loads(line)
                token = payload.get("response", "")
                if token:
                    answer_parts.append(token)
                    yield ("token", token)
                if payload.get("done"):
                    break
        except Exception as e:
            logger.info(f"Streaming Ollama unavailable; using heuristic fallback: {e}")
            fallback_res = self._format_fallback_response(
                prepared["search_query"],
                chunks,
                route,
                n_results_initial,
                alpha,
                session_id
            )
            if session_id and report_id:
                conversation_store.add_message(report_id, session_id, "assistant", fallback_res["answer"])
            yield ("token", fallback_res["answer"])
            meta = {k: v for k, v in fallback_res.items() if k != "answer"}
            yield ("metadata", meta)
            return

        response_text = "".join(answer_parts).strip()
        if not response_text:
            fallback_res = self._format_fallback_response(
                prepared["search_query"],
                chunks,
                route,
                n_results_initial,
                alpha,
                session_id
            )
            yield ("token", fallback_res["answer"])
            meta = {k: v for k, v in fallback_res.items() if k != "answer"}
            yield ("metadata", meta)
            return

        if session_id and report_id:
            conversation_store.add_message(report_id, session_id, "assistant", response_text)
        final_res = self._format_llm_response(response_text, chunks, route, n_results_initial, alpha, session_id)
        meta = {k: v for k, v in final_res.items() if k != "answer"}
        yield ("metadata", meta)

# Singleton helper
rag_chatbot = RAGChatbot()
