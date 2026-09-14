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
        self._local_model = None
        self._fastembed_model = None

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
                # BGE-base-en-v1.5 is 768 dims; NVIDIA model is 1536 dims
                # Keep FastEmbed as fallback only when API fails
                self._fastembed_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
            except Exception as e:
                print(f"FastEmbed not available, falling back to sentence-transformers: {e}")
                self._fastembed_model = False  # Mark as unavailable
        return self._fastembed_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Try API first, fall back to local model on failure
        # Note: For non-NVIDIA asymmetric models, the OpenAI-compatible client
        # will use the model name directly. Fallback to local only if API fails.
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
            print(f"API embedding failed, using local model: {e}")
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
        if self.is_nvidia_asymmetric:
            try:
                resp = self.client.embeddings.create(
                    model=self.model,
                    input=[text],
                    extra_body={"input_type": "query"},
                )
                return tuple(resp.data[0].embedding)
            except Exception as e:
                print(f"API query embedding failed, using local model: {e}")
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