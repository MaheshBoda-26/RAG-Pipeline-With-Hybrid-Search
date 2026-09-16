"""Embedding wrapper with support for OpenAI/NVIDIA APIs and FastEmbed/local fallback."""
from __future__ import annotations

import os
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

    @staticmethod
    def _is_config_error(e: Exception) -> bool:
        """Config errors (bad key / nonexistent model) mean every future API
        call will fail too, so we must stick to one backend instead of
        flapping between the API and a local model."""
        msg = str(e)
        return any(code in msg for code in ("401", "403", "404", "AuthenticationError", "PermissionDenied", "NotFound"))

    def _warn_local_only(self, reason: str) -> None:
        if not self._warned_local_only:
            self._warned_local_only = True
            import logging
            logging.getLogger(__name__).warning(
                "Embedding API misconfigured (%s). Pinning ALL embeddings for "
                "this process to the LOCAL model to keep the vector space "
                "consistent. Fix EMBEDDING_MODEL / the provider API key and "
                "RE-INGEST all documents if you switch back — embeddings from "
                "different models must never be mixed in one collection.", reason
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if not self._use_local_only:
            try:
                out: list[list[float]] = []
                for i in range(0, len(texts), BATCH_SIZE):
                    batch = texts[i : i + BATCH_SIZE]
                    kwargs = {"model": self.model, "input": batch}
                    if self.is_nvidia_asymmetric:
                        kwargs["extra_body"] = {"input_type": "passage"}
                    resp = self.client.embeddings.create(**kwargs)
                    out.extend([d.embedding for d in resp.data])
                return out
            except Exception as e:
                if self._is_config_error(e):
                    # Misconfiguration will recur on every call: stick to the
                    # local model so query and document embeddings always come
                    # from the SAME model (mixed spaces break retrieval).
                    self._use_local_only = True
                    self._warn_local_only(str(e))
                else:
                    print(f"API embedding failed (transient), using local model: {e}")
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
                return embeddings
            except Exception as e:
                print(f"FastEmbed failed, falling back to sentence-transformers: {e}")

        # Fallback to sentence-transformers
        model = self._get_local_model()
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
        if self.expected_dim and embeddings.size > 0 and len(embeddings[0]) != self.expected_dim:
            raise ValueError(
                f"Local model dim {len(embeddings[0])} != expected {self.expected_dim}. "
                f"This will cause Qdrant vector dimension mismatch. "
                f"Ensure embedding model dimensions match Qdrant collection config."
            )
        return embeddings.tolist()

    @lru_cache(maxsize=1000)
    def _cached_embed_one(self, text: str) -> tuple[float, ...]:
        """Cached single query embedding - returns tuple for hashability."""
        # Respect the sticky backend so queries use the SAME model as documents.
        if not self._use_local_only:
            try:
                kwargs = {"model": self.model, "input": [text]}
                if self.is_nvidia_asymmetric:
                    kwargs["extra_body"] = {"input_type": "query"}
                resp = self.client.embeddings.create(**kwargs)
                return tuple(resp.data[0].embedding)
            except Exception as e:
                if self._is_config_error(e):
                    self._use_local_only = True
                    self._warn_local_only(str(e))
                else:
                    print(f"API query embedding failed (transient), using local model: {e}")
        local_emb = self._embed_local([text])[0]
        if self.expected_dim and len(local_emb) != self.expected_dim:
            print(f"WARNING: Local model dim {len(local_emb)} != expected {self.expected_dim}. Queries may fail.")
        return tuple(local_emb)

    def embed_one(self, text: str) -> list[float]:
        """Embed a single query text (with LRU cache)."""
        return list(self._cached_embed_one(text))


def create_openai_client(api_key: str | None = None, base_url: str | None = None) -> OpenAI:
    """Create OpenAI client with optional base_url for NVIDIA NIM."""
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)