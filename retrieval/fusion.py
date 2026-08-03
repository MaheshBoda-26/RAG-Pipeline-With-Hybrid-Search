"""Reciprocal Rank Fusion: combine dense and sparse rankings into one list
without needing their raw scores to be on comparable scales (cosine
similarity and BM25 scores aren't). Each result's fused score is a weighted
sum of 1/(k + rank) across whichever list(s) it appeared in.
"""
from __future__ import annotations


def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3,
    k: int = 60,
) -> list[dict]:
    """Each input is a list of {id, score, payload} already ranked best-first.
    Returns a merged, re-ranked list of {id, payload, fused_score,
    dense_rank, sparse_rank} sorted by fused_score descending."""
    fused: dict[str, dict] = {}

    for rank, item in enumerate(dense_results):
        entry = fused.setdefault(
            item["id"], {"id": item["id"], "payload": item["payload"], "fused_score": 0.0,
                          "dense_rank": None, "sparse_rank": None}
        )
        entry["fused_score"] += dense_weight * (1.0 / (k + rank + 1))
        entry["dense_rank"] = rank + 1

    for rank, item in enumerate(sparse_results):
        entry = fused.setdefault(
            item["id"], {"id": item["id"], "payload": item["payload"], "fused_score": 0.0,
                          "dense_rank": None, "sparse_rank": None}
        )
        entry["fused_score"] += sparse_weight * (1.0 / (k + rank + 1))
        entry["sparse_rank"] = rank + 1

    return sorted(fused.values(), key=lambda e: e["fused_score"], reverse=True)
