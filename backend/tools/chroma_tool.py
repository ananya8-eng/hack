import os
import logging
import numpy as np
from backend.tools.embedding_tool import embedding_manager

logger = logging.getLogger(__name__)

class ChromaDBManager:
    def __init__(self, db_path="./chroma_db"):
        self.db_path = db_path
        self.client = None
        self.collection = None
        self.use_fallback = False
        self.fallback_db = []  # List of dicts: {"id", "document", "embedding", "metadata"}

        try:
            import chromadb
            logger.info(f"Initializing ChromaDB persistent client at: {db_path}")
            self.client = chromadb.PersistentClient(path=db_path)
            self.collection = self.client.get_or_create_collection("filings")
            logger.info("ChromaDB initialized successfully.")
        except Exception as e:
            logger.warning(f"Failed to initialize ChromaDB: {str(e)}. Switching to high-fidelity In-Memory Vector Store fallback.")
            self.use_fallback = True

    def add_chunks(self, chunks: list, metadata_list: list, ids: list):
        """
        Generates embeddings and adds chunks to ChromaDB (or fallback).
        """
        if not chunks:
            return
            
        embeddings = embedding_manager.get_embeddings(chunks)
        
        if self.use_fallback or self.collection is None:
            # Add to in-memory fallback db
            for i, chunk in enumerate(chunks):
                doc_id = ids[i]
                meta = metadata_list[i] if i < len(metadata_list) else {}
                emb = embeddings[i]
                
                # Check for duplicate
                existing = [item for item in self.fallback_db if item["id"] == doc_id]
                if existing:
                    existing[0]["document"] = chunk
                    existing[0]["embedding"] = emb
                    existing[0]["metadata"] = meta
                else:
                    self.fallback_db.append({
                        "id": doc_id,
                        "document": chunk,
                        "embedding": emb,
                        "metadata": meta
                    })
            logger.info(f"Added {len(chunks)} chunks to in-memory Vector DB fallback.")
            return

        try:
            # Add to ChromaDB
            self.collection.upsert(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadata_list,
                ids=ids
            )
            logger.info(f"Added {len(chunks)} chunks to ChromaDB.")
        except Exception as e:
            logger.error(f"Error adding to ChromaDB: {str(e)}. Using fallback database.")
            # Graceful write-thru to fallback
            self.use_fallback = True
            self.add_chunks(chunks, metadata_list, ids)

    def query_similar_chunks(self, query_text: str, n_results: int = 5, where: dict = None, report_id: str = None) -> list:
        """
        Queries the vector store and returns a list of dictionaries with matching chunks:
        [{"document", "metadata", "score", "id"}]
        """
        query_emb = embedding_manager.get_embedding(query_text)
        effective_where = self._merge_where(where, report_id)

        if self.use_fallback or self.collection is None:
            # Manual Cosine Similarity search on in-memory database
            results = []
            if not self.fallback_db:
                return results

            query_vec = np.array(query_emb)
            query_norm = np.linalg.norm(query_vec)

            for item in self.fallback_db:
                # Filter by 'where' metadata filter if present
                if effective_where and not self._metadata_matches(item["metadata"], effective_where):
                    continue

                item_vec = np.array(item["embedding"])
                item_norm = np.linalg.norm(item_vec)
                
                if query_norm > 0 and item_norm > 0:
                    similarity = np.dot(query_vec, item_vec) / (query_norm * item_norm)
                else:
                    similarity = 0.0

                results.append({
                    "document": item["document"],
                    "metadata": item["metadata"],
                    "score": float(similarity),
                    "id": item["id"]
                })

            # Sort by similarity score descending
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:n_results]

        try:
            # Query ChromaDB
            query_params = {
                "query_embeddings": [query_emb],
                "n_results": n_results
            }
            if effective_where:
                query_params["where"] = effective_where

            chroma_results = self.collection.query(**query_params)
            
            formatted_results = []
            if chroma_results and chroma_results.get("documents"):
                docs = chroma_results["documents"][0]
                metas = chroma_results["metadatas"][0] if chroma_results.get("metadatas") else [{}] * len(docs)
                ids = chroma_results["ids"][0] if chroma_results.get("ids") else [""] * len(docs)
                distances = chroma_results["distances"][0] if chroma_results.get("distances") else [0.0] * len(docs)
                
                for i in range(len(docs)):
                    # ChromaDB returns L2 distance. Convert it to a similarity score format
                    # lower distance means higher similarity.
                    score = 1.0 / (1.0 + distances[i])
                    formatted_results.append({
                        "document": docs[i],
                        "metadata": metas[i],
                        "score": score,
                        "id": ids[i]
                    })
            return formatted_results

        except Exception as e:
            logger.error(f"Error querying ChromaDB: {str(e)}. Falling back to in-memory db.")
            self.use_fallback = True
            return self.query_similar_chunks(query_text, n_results, where, report_id)

    def get_collection_stats(self, report_id: str = None) -> dict:
        """
        Returns lightweight collection diagnostics, optionally scoped to one report.
        """
        where = {"report_id": report_id} if report_id else None
        if self.use_fallback or self.collection is None:
            rows = [
                item for item in self.fallback_db
                if not report_id or item.get("metadata", {}).get("report_id") == report_id
            ]
            return self._summarize_rows([row.get("metadata", {}) for row in rows], len(rows))

        try:
            if where:
                data = self.collection.get(where=where, include=["metadatas"])
            else:
                data = self.collection.get(include=["metadatas"])
            metadatas = data.get("metadatas") or []
            return self._summarize_rows(metadatas, len(data.get("ids") or []))
        except Exception as e:
            logger.warning(f"Could not read ChromaDB stats: {e}")
            return {"total_chunks": 0, "sections": {}, "companies": {}, "error": str(e)}

    @staticmethod
    def _merge_where(where: dict = None, report_id: str = None) -> dict:
        effective_where = dict(where or {})
        if report_id:
            effective_where["report_id"] = report_id
        if len(effective_where) > 1:
            return {"$and": [{key: value} for key, value in effective_where.items()]}
        return effective_where

    @classmethod
    def _metadata_matches(cls, metadata: dict, where: dict) -> bool:
        if "$and" in where:
            return all(cls._metadata_matches(metadata, clause) for clause in where["$and"])
        for key, value in where.items():
            if metadata.get(key) != value:
                return False
        return True

    @staticmethod
    def _summarize_rows(metadatas: list, total: int) -> dict:
        sections = {}
        companies = {}
        for meta in metadatas:
            section = meta.get("section", "unknown")
            company = meta.get("company", "unknown")
            sections[section] = sections.get(section, 0) + 1
            companies[company] = companies.get(company, 0) + 1
        return {
            "total_chunks": total,
            "sections": sections,
            "companies": companies
        }

# Singleton helper
chromadb_manager = ChromaDBManager()
