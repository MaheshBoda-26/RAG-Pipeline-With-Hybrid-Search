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
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = os.getenv("CHAT_MODEL", "gpt-4o")

    # --- Storage ---
    qdrant_path: str = os.getenv("QDRANT_PATH", "./qdrant_data")
    qdrant_url: str = os.getenv("QDRANT_URL", "")  # if set, use remote server instead of embedded
    collection_name: str = "docs"
    embedding_dim: int = 1536  # text-embedding-3-small

    # --- Chunking ---
    chunking_strategy: str = os.getenv("CHUNK_STRATEGY", "recursive")  # fixed | recursive | semantic
    fixed_chunk_size: int = 800
    fixed_chunk_overlap: int = 120
    semantic_similarity_threshold: float = 0.28  # higher = fewer, larger chunks

    # --- Dedup ---
    dedup_similarity_threshold: float = 0.95

    # --- Retrieval ---
    dense_top_k: int = 10
    sparse_top_k: int = 10
    rrf_k: int = 60  # RRF damping constant
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    rerank_candidate_pool: int = 20
    final_top_k: int = 5

    # --- Confidence / fallback ---
    min_retrieval_confidence: float = 0.35  # below this, refuse rather than hallucinate

    def validate(self):
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
            )


settings = Settings()
