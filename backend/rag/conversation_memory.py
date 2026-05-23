import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ConversationMemory:
    """
    In-memory store for multi-turn RAG conversation context.
    Keyed by (report_id, session_id).
    Supports context compression and coreference resolution hints.
    """
    def __init__(self):
        # { report_id: { session_id: [ {role: "user"|"assistant", content: str, timestamp: float} ] } }
        self._store = {}
        self.max_turns = 10  # Maximum conversational turns to retain

    def add_message(self, report_id: str, session_id: str, role: str, content: str):
        if report_id not in self._store:
            self._store[report_id] = {}
        if session_id not in self._store[report_id]:
            self._store[report_id][session_id] = []
            
        history = self._store[report_id][session_id]
        
        history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        
        # Enforce max length to prevent context window bloat
        if len(history) > self.max_turns * 2:  # *2 because turn = user+assistant
            self._store[report_id][session_id] = history[-(self.max_turns * 2):]

    def get_history(self, report_id: str, session_id: str) -> List[Dict]:
        return self._store.get(report_id, {}).get(session_id, [])

    def get_all_sessions(self, report_id: str) -> Dict[str, List[Dict]]:
        return self._store.get(report_id, {})

    def format_history_for_prompt(self, report_id: str, session_id: str, max_tokens_est: int = 1000) -> str:
        """
        Formats recent history into a condensed string block for the LLM prompt.
        """
        history = self.get_history(report_id, session_id)
        if not history:
            return ""
            
        # We only want the last ~3 full turns to avoid diluting the context window
        recent_history = history[-6:] 
        
        formatted = []
        for msg in recent_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            formatted.append(f"[{role}]: {msg['content']}")
            
        return "\n".join(formatted)
        
    def contextualize_query(self, query: str, report_id: str, session_id: str) -> str:
        """
        Simple coreference resolution heuristic.
        If the query is just "what about AMD?" or "how does that impact revenue?",
        we append a hint of the previous topic to help vector search.
        """
        history = self.get_history(report_id, session_id)
        if not history:
            return query
            
        # If query is short and contains pronouns/referential words, inject last user topic
        query_lower = query.lower()
        referential_words = ["it", "they", "them", "that", "those", "these", "he", "she", "this"]
        
        has_referential = any(f" {w} " in f" {query_lower} " for w in referential_words)
        is_short = len(query.split()) < 8
        
        if (has_referential or is_short) and len(history) >= 2:
            # Find last user question
            last_user_q = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
            if last_user_q:
                # Extract key nouns/entities from last query (simple heuristic)
                words = [w for w in last_user_q.split() if len(w) > 4 and w.lower() not in ["what", "how", "why", "when", "where", "which"]]
                if words:
                    context_hint = " ".join(words[:3])
                    logger.debug(f"Contextualizing query: '{query}' + '{context_hint}'")
                    return f"{query} (Context: {context_hint})"
                    
        return query

# Singleton
conversation_store = ConversationMemory()
