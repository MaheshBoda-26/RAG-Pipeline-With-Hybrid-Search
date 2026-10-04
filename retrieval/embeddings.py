"""Embedding wrapper with support for OpenAI/NVIDIA APIs and FastEmbed/local fallback."""
from __future__ import annotations

from functools import lru_cache
from openai import OpenAI

BATCH_SIZE = 128


class Embedder:
    def __init__(self, client: OpenAI, model: str, expected_dim: int | None = None):
        self.client = client
        self.model = model
        self.expected_dim = expected_dim
        # NVIDIA asymmetric embedding models require input_type
        self.is_nvidia_asymmetric = "nvidia/nv-embedqa" in model or "nvidia/llama-nemotron-embed" in model
        # BGE models don't need input_type
        self.is_bge_model = "bge-" in model.lower()
        self._local_model = None
        self._fastembed_model = None
        # Sticky backend selection: once the API is found to be misconfigured
        # (bad key / nonexistent model), pin ALL embeddings for this Embedder
        # instance to the local model. Mixing API and local embeddings in the
        # same vector space silently corrupts dense retrieval (documents and
        # queries would live in different spaces and never match), so the
        # first failure decides the backend for the process lifetime.
        self._use_local_only = False
        self._warned_local_only = False
        self._embedding_identity: str | None = None
        self._prefer_local = model.lower().startswith(("baai/", "sentence-transformers/"))

    @property
    def embedding_identity(self) -> str:
        """Return the implementation that actually produced the vectors."""
        return self._embedding_identity or f"unresolved:{self.model}"

    def _pin_to_local(self, reason: str) -> None:
        self._use_local_only = True
        # A cached remote query vector must not survive switching to a local
        # backend; it would be compared with vectors from a different space.
        self._cached_embed_one.cache_clear()
        self._warn_local_only(reason)

    def _get_local_model(self):
        """Lazy-load local sentence-transformers model."""
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            # Use a good general-purpose model that works well for RAG
            self._local_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        return self._local_model

    def _get_fastembed_model(self):
        """Lazy-load FastEmbed model (faster than sentence-transformers)."""
        if self._fastembed_model is None:
            try:
                from fastembed import TextEmbedding
                # BGE-base-en-v1.5 is 768 dims - matches our default config
                self._fastembed_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
            except Exception as e:
                print(f"FastEmbed not available, falling back to sentence-transformers: {e}")
                self._fastembed_model = False  # Mark as unavailable
        return self._fastembed_model

    def _warn_local_only(self, reason: str) -> None:
        if not self._warned_local_only:
            self._warned_local_only = True
            import logging
            logging.getLogger(__name__).warning(
                "Embedding API unavailable (%s). Pinning ALL embeddings for "
                "this process to the LOCAL model to keep the vector space "
                "consistent. Fix EMBEDDING_MODEL / the provider API key and "
                "RE-INGEST all documents if you switch back — embeddings from "
                "different models must never be mixed in one collection.", reason
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if not self._use_local_only and not self._prefer_local:
            try:
                out: list[list[float]] = []
                for i in range(0, len(texts), BATCH_SIZE):
                    batch = texts[i : i + BATCH_SIZE]
                    kwargs = {"model": self.model, "input": batch}
                    if self.is_nvidia_asymmetric:
                        kwargs["extra_body"] = {"input_type": "passage"}
                    resp = self.client.embeddings.create(**kwargs)
                    self._embedding_identity = f"api:{self.client.base_url}:{self.model}"
                    out.extend([d.embedding for d in resp.data])
                return out
            except Exception as e:
                # Pin on every failure, including transient errors, so separate
                # batches and later queries cannot silently use different spaces.
                self._pin_to_local(str(e))
        return self._embed_local(texts)

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Embed using FastEmbed (preferred) or sentence-transformers fallback."""
        # Try FastEmbed first (5-10x faster)
        fastembed = self._get_fastembed_model()
        if fastembed and fastembed is not False:
            try:
                # FastEmbed returns a generator, convert to list
                embeddings = list(fastembed.embed(texts))
                if self.expected_dim and embeddings and len(embeddings[0]) != self.expected_dim:
                    raise ValueError(
                        f"FastEmbed dim {len(embeddings[0])} != expected {self.expected_dim}. "
                        f"This will cause Qdrant vector dimension mismatch. "
                        f"Ensure embedding model dimensions match Qdrant collection config."
                    )
                self._embedding_identity = "fastembed:BAAI/bge-base-en-v1.5"
                return embeddings
            except Exception as e:
                print(f"FastEmbed failed, falling back to sentence-transformers: {e}")

        # Fallback to sentence-transformers
        model = self._get_local_model()
        self._embedding_identity = "sentence-transformers/all-mpnet-base-v2"
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
        if self.expected_dim and embeddings.size > 0 and len(embeddings[0]) != self.expected_dim:
            raise ValueError(
                f"Local model dim {len(embeddings[0])} != expected {self.expected_dim}. "
                f"This will cause Qdrant vector dimension mismatch. "
                f"Ensure embedding model dimensions match Qdrant collection config."
            )
        return embeddings.tolist()

    # Intentional per-instance cache: bounded, and Embedder instances are
    # long-lived singletons per process (see create_openai_client).
    @lru_cache(maxsize=1000)  # noqa: B019
    def _cached_embed_one(self, text: str) -> tuple[float, ...]:
        """Cached single query embedding - returns tuple for hashability."""
        # Respect the sticky backend so queries use the SAME model as documents.
        if not self._use_local_only and not self._prefer_local:
            try:
                kwargs = {"model": self.model, "input": [text]}
                if self.is_nvidia_asymmetric:
                    kwargs["extra_body"] = {"input_type": "query"}
                resp = self.client.embeddings.create(**kwargs)
                self._embedding_identity = f"api:{self.client.base_url}:{self.model}"
                return tuple(resp.data[0].embedding)
            except Exception as e:
                self._pin_to_local(str(e))
        local_emb = self._embed_local([text])[0]
        if self.expected_dim and len(local_emb) != self.expected_dim:
            print(f"WARNING: Local model dim {len(local_emb)} != expected {self.expected_dim}. Queries may fail.")
        return tuple(local_emb)

    def embed_one(self, text: str) -> list[float]:
        """Embed a single query text (with LRU cache)."""
        return list(self._cached_embed_one(text))


def create_openai_client(api_key: str | None = None, base_url: str | None = None) -> OpenAI:
    """Create OpenAI client with optional base_url for NVIDIA NIM.

    Latency guardrails: without an explicit timeout the SDK waits up to 10
    minutes per call, and with the default max_retries=2 a transient NVIDIA
    error silently adds two backoff retries to a user's wait — observed as
    25 s answers. One retry with a 30 s ceiling keeps transient-error
    resilience while capping the worst-case wall clock.
    """
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    kwargs.setdefault("timeout", 30.0)
    kwargs.setdefault("max_retries", 1)
    return OpenAI(**kwargs)
