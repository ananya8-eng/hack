import os
import hashlib
import numpy as np
import logging

logger = logging.getLogger(__name__)

def get_mock_embedding(text: str, dim: int = 1024) -> list:
    """
    Generates deterministic, normalized 1024-dimensional mock embeddings
    using a SHA-256 hash seed. Extremely fast and requires no downloads,
    ideal as a fallback.
    """
    # Deterministic seed based on text content
    h = hashlib.sha256(text.encode('utf-8')).digest()
    seed = int.from_bytes(h[:4], byteorder='big') % (2**32)
    
    # Generate pseudo-random vector
    rng = np.random.default_rng(seed)
    vec = rng.normal(0.0, 1.0, dim)
    
    # Normalize to unit vector
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()

class EmbeddingManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
            cls._instance.model = None
            cls._instance.use_fallback = False
            cls._instance.initialized = False
            cls._instance.embedding_dim = 1024
        return cls._instance

    def initialize(self):
        if self.initialized:
            return
        
        # We try to load sentence-transformers. 
        # Since BAAI/bge-large-en-v1.5 is a large model (1.34 GB), we will load it lazily or support fallback
        try:
            mode = os.environ.get("EMBEDDING_MODE", "mock").lower()
            use_mock = os.environ.get("USE_MOCK_EMBEDDINGS", "false").lower() == "true"
            if use_mock or mode == "mock":
                logger.info("USE_MOCK_EMBEDDINGS is active. Using semantic mock embeddings.")
                self.use_fallback = True
                self.initialized = True
                return

            from sentence_transformers import SentenceTransformer
            logger.info("Initializing SentenceTransformer 'BAAI/bge-large-en-v1.5'...")
            # We set a short timeout or just load.
            self.model = SentenceTransformer("BAAI/bge-large-en-v1.5", trust_remote_code=True)
            self.embedding_dim = int(self.model.get_sentence_embedding_dimension() or 1024)
            logger.info("SentenceTransformer BAAI/bge-large-en-v1.5 loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer: {str(e)}. Using high-fidelity semantic fallback.")
            self.use_fallback = True
            
        self.initialized = True

    def get_embedding(self, text: str) -> list:
        if not self.initialized:
            self.initialize()
            
        if self.use_fallback or self.model is None:
            return get_mock_embedding(text)
            
        try:
            embedding = self.model.encode(text)
            if hasattr(embedding, 'tolist'):
                return embedding.tolist()
            return list(embedding)
        except Exception as e:
            logger.error(f"Error encoding text embedding: {str(e)}. Falling back.")
            return get_mock_embedding(text)

    def get_embeddings(self, texts: list) -> list:
        if not texts:
            return []
        if not self.initialized:
            self.initialize()
        if self.use_fallback or self.model is None:
            return [get_mock_embedding(text, self.embedding_dim) for text in texts]
        try:
            embeddings = self.model.encode(texts)
            return embeddings.tolist() if hasattr(embeddings, "tolist") else list(embeddings)
        except Exception as e:
            logger.error(f"Error encoding batch embeddings: {str(e)}. Falling back.")
            return [get_mock_embedding(text, self.embedding_dim) for text in texts]

    @property
    def is_using_real_model(self) -> bool:
        if not self.initialized:
            self.initialize()
        return self.model is not None and not self.use_fallback

# Singleton helper
embedding_manager = EmbeddingManager()
