"""Central configuration for the RAG pipeline.

All tunables live here so retrieval/generation behavior can be adjusted
without touching pipeline logic, and so eval runs can sweep these values.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # --- Providers ---
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    chat_model: str = os.getenv("CHAT_MODEL", "gpt-4o")

    # --- Storage ---
    qdrant_path: str = os.getenv("QDRANT_PATH", "./qdrant_data")
    qdrant_url: str = os.getenv("QDRANT_URL", "")  # if set, use remote server instead of embedded
    collection_name: str = os.getenv("COLLECTION_NAME", "docs")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    # --- Chunking ---
    chunking_strategy: str = os.getenv("CHUNK_STRATEGY", "recursive")  # fixed | recursive | semantic
    fixed_chunk_size: int = int(os.getenv("FIXED_CHUNK_SIZE", "800"))
    fixed_chunk_overlap: int = int(os.getenv("FIXED_CHUNK_OVERLAP", "120"))
    semantic_similarity_threshold: float = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.28"))

    # --- Dedup ---
    dedup_similarity_threshold: float = float(os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.95"))

    # --- Retrieval ---
    dense_top_k: int = int(os.getenv("DENSE_TOP_K", "10"))
    sparse_top_k: int = int(os.getenv("SPARSE_TOP_K", "10"))
    rrf_k: int = int(os.getenv("RRF_K", "60"))
    dense_weight: float = float(os.getenv("DENSE_WEIGHT", "0.7"))
    sparse_weight: float = float(os.getenv("SPARSE_WEIGHT", "0.3"))
    rerank_candidate_pool: int = int(os.getenv("RERANK_CANDIDATE_POOL", "20"))
    final_top_k: int = int(os.getenv("FINAL_TOP_K", "5"))

    # --- Confidence / fallback ---
    min_retrieval_confidence: float = float(os.getenv("MIN_RETRIEVAL_CONFIDENCE", "0.35"))

    # --- Auth ---
    api_key: str = os.getenv("API_KEY", "dev-secret-key")
    allowed_ingest_root: str = os.getenv("ALLOWED_INGEST_ROOT", "./sample_docs")

    def validate(self):
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
            )


settings = Settings()
