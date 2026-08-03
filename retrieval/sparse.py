"""BM25 keyword search. Catches exact matches on function names, config keys,
error codes -- the kind of tokens dense embeddings tend to blur together."""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

TOKEN_RE = re.compile(r"[a-zA-Z0-9_./\-]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


class BM25Index:
    def __init__(self):
        self.bm25: BM25Okapi | None = None
        self.ids: list[str] = []
        self.payloads: list[dict] = []

    def build(self, records: list[dict]) -> None:
        """`records`: list of {id, payload} where payload has a 'text' field.
        Rebuilds the index from scratch -- called after every ingest so it
        never drifts out of sync with the vector store."""
        self.ids = [r["id"] for r in records]
        self.payloads = [r["payload"] for r in records]
        corpus = [tokenize(r["payload"]["text"]) for r in records]
        self.bm25 = BM25Okapi(corpus) if corpus else None

    def query(self, query_text: str, top_k: int) -> list[dict]:
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(tokenize(query_text))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            {"id": self.ids[i], "score": float(scores[i]), "payload": self.payloads[i]}
            for i in ranked
            if scores[i] > 0
        ]
