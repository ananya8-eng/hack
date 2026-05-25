import logging
import re

from backend.agents.llm_client import llm_client
from backend.guardrails import guardrails
from backend.agents.slm_system_prompts import SlmRole, compose_slm_prompt, user_query_reminder
from backend.rag.citation_sources import (
    citation_from_chroma_chunk,
    summarize_source_types,
)
from backend.tools.vector_store import vector_store as chromadb_manager

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
            citations.append(
                citation_from_chroma_chunk(
                    {"document": doc, "metadata": meta},
                    chunk_idx,
                )
            )
            citation_id = citations[-1]["citation_id"]
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
            
            citations.append(
                citation_from_chroma_chunk(top_item, chunk_idx)
            )
            citation_id = citations[-1]["citation_id"]
            
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
            answer_parts.append(f"• {sent} {cit}")
            added_points += 1
            
        answer = " ".join(answer_parts)
        if len(evidence_sentences) > 3:
            answer += f" Additional structural indicators are mentioned in other parts of the filing."

    return {
        "answer": answer,
        "citations": citations,
        "source_summary": summarize_source_types(citations),
        "success": True,
    }

class RAGChatbot:
    def query_chatbot(self, user_question: str, company_name: str = None) -> dict:
        """
        Retrieves top relevant chunks from Qdrant and uses Qwen (or Heuristic RAG)
        to answer with precise inline citations, avoiding hallucinations.
        """
        input_guard = guardrails.check_chat_message(user_question)
        if not input_guard.allowed:
            payload = input_guard.to_api_payload()
            payload["mode"] = "rag"
            return payload

        user_question = input_guard.sanitized_text or user_question
        logger.info(f"RAG Chatbot processing question: '{user_question}'...")
        
        # Determine query filter
        where_filter = None
        if company_name:
            where_filter = {"company": company_name}

        # Query top 4 chunks
        chunks = chromadb_manager.query_similar_chunks(user_question, n_results=4, where=where_filter)
        
        if not chunks:
            # Try a broader search across all companies
            chunks = chromadb_manager.query_similar_chunks(user_question, n_results=4)
            
        logger.info(f"Retrieved {len(chunks)} relevant chunks from Qdrant.")

        # Formulate context block
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

        task_body = f"""
        {user_query_reminder(user_question)}

        [Retrieved Filing Contexts — uploaded_filing / vector_db only]
        {context_text}

        [Task]
        Answer the user query in prose with inline bracket citations for every factual claim.
        If the contexts are insufficient, respond with exactly:
        "I cannot find sufficient evidence in the retrieved filings to answer this."
        Do not request tools; retrieval is already complete for this turn.
        """
        prompt = compose_slm_prompt(SlmRole.RAG_CHAT, task_body)

        response_text = llm_client.generate(prompt, temperature=0.1, timeout=60)

        if not response_text:
            return {
                "answer": (
                    "I could not produce a safe, evidence-backed answer. "
                    "Rephrase your filing question or try again."
                ),
                "citations": [],
                "success": False,
                "guardrail_blocked": True,
            }

        output_guard = guardrails.check_llm_text_output(response_text)
        if not output_guard.allowed:
            payload = output_guard.to_api_payload()
            payload["mode"] = "rag"
            return payload
        response_text = output_guard.sanitized_text or response_text

        if response_text and len(response_text.strip()) > 50:
            citations = [
                citation_from_chroma_chunk(item, i) for i, item in enumerate(chunks)
            ]

            return {
                "answer": response_text.strip(),
                "citations": citations,
                "source_summary": summarize_source_types(citations),
                "success": True,
            }

        # ==========================================
        # HEURISTIC RAG FALLBACK
        # ==========================================
        logger.info("Executing Heuristic RAG Q&A Engine...")
        heuristic = generate_heuristic_rag_answer(user_question, chunks)
        out_guard = guardrails.check_llm_text_output(heuristic.get("answer", ""))
        if not out_guard.allowed:
            payload = out_guard.to_api_payload()
            payload["mode"] = "rag"
            return payload
        if out_guard.sanitized_text:
            heuristic = {**heuristic, "answer": out_guard.sanitized_text}
        if not heuristic.get("source_summary"):
            heuristic["source_summary"] = summarize_source_types(
                heuristic.get("citations") or []
            )
        return heuristic

# Singleton helper
rag_chatbot = RAGChatbot()
