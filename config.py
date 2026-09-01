"""Central configuration for the RAG pipeline.

All tunables live here so retrieval/generation behavior can be adjusted
without touching pipeline logic, and so eval runs can sweep these values.
"""
import os
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# User registry file for persistence
USER_REGISTRY_PATH = Path("./user_registry.json")

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(64))
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


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


def create_user(name: str, email: str | None = None, password: str | None = None, role: str = "user") -> tuple[str, str]:
    """Create a new user. Returns (user_id, api_key)."""
    user_id = f"user_{secrets.token_urlsafe(8)}"
    api_key = f"sk_{secrets.token_urlsafe(32)}"
    registry = load_user_registry()
    user_data = {
        "name": name,
        "email": email or name,
        "api_key": api_key,
        "created": datetime.now().isoformat(),
        "role": role,
    }
    if password:
        import bcrypt
        user_data["password_hash"] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    registry[user_id] = user_data
    save_user_registry(registry)
    return user_id, api_key


def verify_user_password(user_id: str, password: str) -> bool:
    """Verify user password using bcrypt."""
    import bcrypt
    registry = load_user_registry()
    user = registry.get(user_id)
    if not user or "password_hash" not in user:
        return False
    return bcrypt.checkpw(password.encode(), user["password_hash"].encode())


def get_user_by_email(email: str) -> str | None:
    """Look up user_id by email (stored as email field or name for backward compat)."""
    registry = load_user_registry()
    for uid, info in registry.items():
        if info.get("email") == email or info.get("name") == email:
            return uid
    return None


# JWT token functions
def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    from jose import jwt
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create JWT refresh token."""
    from jose import jwt
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate JWT token."""
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> str | None:
    """Extract user_id from JWT token."""
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return payload.get("sub")
    return None


@dataclass
class Settings:
    # --- Providers ---
    nvidia_api_key: str = field(default_factory=lambda: os.getenv("NVIDIA_API_KEY", ""))
    nvidia_base_url: str = field(default_factory=lambda: os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5")
    chat_model: str = os.getenv("CHAT_MODEL", "meta/llama-3.1-70b-instruct")

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
    jwt_secret: str = JWT_SECRET
    jwt_algorithm: str = JWT_ALGORITHM
    access_token_expire_minutes: int = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expire_days: int = JWT_REFRESH_TOKEN_EXPIRE_DAYS

    # --- Upload limits ---
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

    # --- Cookie security ---
    environment: str = os.getenv("ENVIRONMENT", "development")
    cookie_secure: bool = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development") == "production")
    cookie_domain: str = field(default_factory=lambda: os.getenv("COOKIE_DOMAIN", ""))

    # --- Supabase ---
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    supabase_db_url: str = os.getenv("SUPABASE_DB_URL", "")
    use_supabase: bool = field(default_factory=lambda: os.getenv("USE_SUPABASE", "false").lower() == "true")

    def validate(self):
        if not self.nvidia_api_key:
            raise RuntimeError(
                "NVIDIA_API_KEY is not set. Copy .env.example to .env and fill it in."
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
