"""Central configuration for the RAG pipeline.

All tunables live here so retrieval/generation behavior can be adjusted
without touching pipeline logic, and so eval runs can sweep these values.
"""
import os
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# User registry file for persistence
USER_REGISTRY_PATH = Path("./user_registry.json")


def load_user_registry() -> dict:
    if USER_REGISTRY_PATH.exists():
        return json.loads(USER_REGISTRY_PATH.read_text())
    return {}


def save_user_registry(registry: dict) -> None:
    USER_REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


def get_user_by_api_key(api_key: str) -> str | None:
    """Look up user_id by API key."""
    registry = load_user_registry()
    for uid, info in registry.items():
        if info.get("api_key") == api_key:
            return uid
    return None


def create_user(name: str) -> tuple[str, str]:
    """Create a new user. Returns (user_id, api_key)."""
    user_id = f"user_{secrets.token_urlsafe(8)}"
    api_key = f"sk_{secrets.token_urlsafe(32)}"
    registry = load_user_registry()
    registry[user_id] = {"name": name, "api_key": api_key, "created": __import__("datetime").datetime.now().isoformat()}
    save_user_registry(registry)
    return user_id, api_key


@dataclass
class Settings:
    # --- Providers ---
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", ""))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    chat_model: str = os.getenv("CHAT_MODEL", "gpt-4o")

    # --- Storage ---
    qdrant_path: str = os.getenv("QDRANT_PATH", "./qdrant_data")
    qdrant_url: str = os.getenv("QDRANT_URL", "")  # if set, use remote server instead of embedded
    collection_name: str = os.getenv("COLLECTION_NAME", "docs")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    # --- Multi-tenant ---
    enable_multi_tenant: bool = os.getenv("ENABLE_MULTI_TENANT", "false").lower() == "true"
    user_collection_prefix: str = os.getenv("USER_COLLECTION_PREFIX", "user_")
    default_user_id: str = os.getenv("DEFAULT_USER_ID", "default")

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

    # --- Upload limits ---
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

    def validate(self):
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
            )

    def get_collection_name(self, user_id: str | None = None) -> str:
        """Get collection name for a user. If multi-tenant disabled or no user_id, use default."""
        if self.enable_multi_tenant and user_id:
            return f"{self.user_collection_prefix}{user_id}"
        return self.collection_name

    def get_user_upload_dir(self, user_id: str) -> Path:
        """Get user-specific upload directory."""
        base = Path(self.allowed_ingest_root)
        if self.enable_multi_tenant:
            return base / user_id / "uploads"
        return base


settings = Settings()
