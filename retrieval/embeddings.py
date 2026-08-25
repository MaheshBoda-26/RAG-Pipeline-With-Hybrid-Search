"""Embedding wrapper with support for OpenAI/NVIDIA APIs and local sentence-transformers fallback."""
from __future__ import annotations

import os
from openai import OpenAI

BATCH_SIZE = 128


class Embedder:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model
        # NVIDIA asymmetric embedding models require input_type
        self.is_nvidia_asymmetric = "nvidia/nv-embedqa" in model or "nvidia/llama-nemotron-embed" in model
        self._local_model = None

    def _get_local_model(self):
        """Lazy-load local sentence-transformers model."""
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            # Use a good general-purpose model that works well for RAG
            self._local_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        return self._local_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Try API first, fall back to local
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
        """Embed using local sentence-transformers model."""
        model = self._get_local_model()
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_one(self, text: str) -> list[float]:
        """Embed a single query text."""
        if self.is_nvidia_asymmetric:
            try:
                resp = self.client.embeddings.create(
                    model=self.model,
                    input=[text],
                    extra_body={"input_type": "query"},
                )
                return resp.data[0].embedding
            except Exception as e:
                print(f"API query embedding failed, using local model: {e}")
        return self._embed_local([text])[0]


def create_openai_client(api_key: str | None = None, base_url: str | None = None) -> OpenAI:
    """Create OpenAI client with optional base_url for NVIDIA NIM."""
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)
