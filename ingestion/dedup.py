"""Skip inserting a chunk if it's a near-duplicate of one already indexed.
Prevents the same boilerplate/paragraph appearing in multiple source docs
from eating multiple context-window slots at retrieval time.
"""
from __future__ import annotations

import numpy as np


class DuplicateIndex:
    """Incremental near-duplicate checker. Keeps all accepted embeddings in
    memory and checks new ones against them with cosine similarity. O(n) per
    check, which is fine for the corpus sizes this project targets; swap for
    an ANN index if the corpus grows past ~100k chunks."""

    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold
        self._vectors: list[np.ndarray] = []

    def is_duplicate(self, embedding: list[float]) -> bool:
        if not self._vectors:
            return False
        vec = np.array(embedding)
        vec_norm = np.linalg.norm(vec)
        if vec_norm == 0:
            return False
        vec = vec / vec_norm
        matrix = np.stack(self._vectors)
        sims = matrix @ vec
        return bool(np.max(sims) >= self.threshold)

    def add(self, embedding: list[float]) -> None:
        vec = np.array(embedding)
        norm = np.linalg.norm(vec)
        if norm == 0:
            return
        self._vectors.append(vec / norm)

    def filter_new(
        self, embeddings: list[list[float]]
    ) -> tuple[list[int], list[int]]:
        """Given a batch of embeddings, return (keep_indices, duplicate_indices),
        checking each against both the running index AND earlier items in this
        same batch (so duplicates *within* one ingest run are also caught)."""
        keep, dup = [], []
        for i, emb in enumerate(embeddings):
            if self.is_duplicate(emb):
                dup.append(i)
            else:
                keep.append(i)
                self.add(emb)
        return keep, dup
