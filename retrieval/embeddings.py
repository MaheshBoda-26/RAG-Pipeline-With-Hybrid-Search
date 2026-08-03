"""Thin wrapper around the OpenAI embeddings endpoint with batching."""
from __future__ import annotations

from openai import OpenAI

BATCH_SIZE = 128


class Embedder:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            out.extend([d.embedding for d in resp.data])
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
