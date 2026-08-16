"""Thin wrapper around the OpenAI embeddings endpoint with batching."""
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

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            kwargs = {"model": self.model, "input": batch}
            if self.is_nvidia_asymmetric:
                kwargs["extra_body"] = {"input_type": "passage"}
            resp = self.client.embeddings.create(**kwargs)
            out.extend([d.embedding for d in resp.data])
        return out

    def embed_one(self, text: str) -> list[float]:
        """Embed a single query text (uses query input_type for NVIDIA models)."""
        if self.is_nvidia_asymmetric:
            resp = self.client.embeddings.create(
                model=self.model,
                input=[text],
                extra_body={"input_type": "query"},
            )
            return resp.data[0].embedding
        return self.embed([text])[0]


def create_openai_client(api_key: str | None = None, base_url: str | None = None) -> OpenAI:
    """Create OpenAI client with optional base_url for NVIDIA NIM."""
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)
