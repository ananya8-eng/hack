import logging

import numpy as np

from backend.config import get_settings
from backend.tools.embedding_tool import embedding_manager

logger = logging.getLogger(__name__)


def _flatten_embedding(embedding: list) -> list:
    """Chroma expects a flat list of floats per vector, not nested lists."""
    flat = embedding
    while flat and isinstance(flat[0], list):
        if len(flat) != 1:
            break
        flat = flat[0]
    return flat


_CHROMA_OPERATORS = {"$and", "$or", "$not", "$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin"}


def _normalize_where_for_chroma(where: dict | None) -> dict | None:
    """
    Chroma rejects a multi-key plain dict like {"company": "X", "section": "Y"}
    because it expects exactly one top-level operator. Wrap multi-key filters
    in an explicit $and clause.
    """
    if not where:
        return None
    if len(where) <= 1:
        return where
    if any(k in _CHROMA_OPERATORS for k in where.keys()):
        return where
    return {"$and": [{k: v} for k, v in where.items()]}


def _flatten_where_for_memory(where: dict | None) -> dict:
    """
    Collapse a Chroma-style where clause (possibly using $and with simple equality
    sub-clauses) into a flat {field: value} dict for the in-memory fallback path.
    Operators other than $and / direct equality are dropped to stay safe.
    """
    if not where:
        return {}
    if "$and" in where and isinstance(where["$and"], list):
        flat = {}
        for sub in where["$and"]:
            if isinstance(sub, dict):
                for k, v in sub.items():
                    if k not in _CHROMA_OPERATORS and not isinstance(v, dict):
                        flat[k] = v
        return flat
    return {k: v for k, v in where.items() if k not in _CHROMA_OPERATORS and not isinstance(v, dict)}


class ChromaDBManager:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_settings().chroma_db_path
        self.client = None
        self.collection = None
        self.use_fallback = False
        self.fallback_db = []  # List of dicts: {"id", "document", "embedding", "metadata"}

        try:
            import chromadb
            logger.info("Initializing ChromaDB persistent client at: %s", self.db_path)
            self.client = chromadb.PersistentClient(path=self.db_path)
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
            
        embeddings = [
            _flatten_embedding(emb)
            for emb in embedding_manager.get_embeddings(chunks)
        ]

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

    def query_similar_chunks(self, query_text: str, n_results: int = 5, where: dict = None) -> list:
        """
        Queries the vector store and returns a list of dictionaries with matching chunks:
        [{"document", "metadata", "score", "id"}]
        """
        query_emb = _flatten_embedding(embedding_manager.get_embedding(query_text))

        if self.use_fallback or self.collection is None:
            # Manual Cosine Similarity search on in-memory database
            results = []
            if not self.fallback_db:
                return results

            query_vec = np.array(query_emb)
            query_norm = np.linalg.norm(query_vec)

            flat_where = _flatten_where_for_memory(where)

            for item in self.fallback_db:
                # Filter by 'where' metadata filter if present
                if flat_where:
                    skip = False
                    for k, v in flat_where.items():
                        if item["metadata"].get(k) != v:
                            skip = True
                            break
                    if skip:
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
            normalized_where = _normalize_where_for_chroma(where)
            query_params = {
                "query_embeddings": [query_emb],
                "n_results": n_results
            }
            if normalized_where:
                query_params["where"] = normalized_where

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
            return self.query_similar_chunks(query_text, n_results, where)

# Singleton helper
chromadb_manager = ChromaDBManager()
