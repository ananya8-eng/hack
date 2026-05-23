import re
import json
import logging
import requests
from backend.tools.chroma_tool import chromadb_manager

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
            answer_parts.append(f"• {sent} {cit}")
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

    def query_chatbot(self, user_question: str, company_name: str = None) -> dict:
        """
        Retrieves top relevant chunks from ChromaDB and uses Qwen (or Heuristic RAG)
        to answer with precise inline citations, avoiding hallucinations.
        """
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
            
        logger.info(f"Retrieved {len(chunks)} relevant chunks from ChromaDB.")

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

        prompt = f"""
        [System] You are an elite, citation-backed Financial RAG Chatbot. 
        Your primary directive is to answer the user's question STRICTLY using the provided filing contexts.
        
        [Rules]
        1. Answer ONLY using the facts from the context. Do NOT hallucinate.
        2. Provide precise inline citations citing the sources in brackets, e.g., [NVIDIA Risk Factors - Chunk 4].
        3. If the context does not contain enough information to answer, state clearly: "I cannot find sufficient evidence in the retrieved filings to answer this." Do not make up facts.
        
        [Retrieved Filing Contexts]
        {context_text}
        
        [User Question]
        {user_question}
        
        [Task]
        Synthesize your comprehensive response with citations.
        """

        response_text = self._call_ollama(prompt)
        
        if response_text and len(response_text.strip()) > 50:
            # Build citations list for UI display
            citations = []
            for item in chunks:
                meta = item.get("metadata", {})
                sec = meta.get("section", "Section").replace("_", " ").title()
                comp = meta.get("company", "Company")
                chunk_idx = meta.get("chunk_index", 0)
                
                citations.append({
                    "citation_id": f"[{comp} {sec} - Chunk {chunk_idx}]",
                    "section": sec,
                    "company": comp,
                    "chunk_index": chunk_idx,
                    "content": item.get("document")[:300] + "..."
                })
            
            return {
                "answer": response_text.strip(),
                "citations": citations,
                "success": True
            }

        # ==========================================
        # HEURISTIC RAG FALLBACK
        # ==========================================
        logger.info("Executing Heuristic RAG Q&A Engine...")
        return generate_heuristic_rag_answer(user_question, chunks)

# Singleton helper
rag_chatbot = RAGChatbot()
