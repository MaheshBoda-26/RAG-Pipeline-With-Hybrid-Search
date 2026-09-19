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
        # Carry the raw dense cosine similarity through so the downstream
        # confidence blend can use it (cross-encoder scores are lexically
        # strict and need this as an independent second signal).
        if item.get("score") is not None:
            entry["dense_score"] = float(item["score"])

    for rank, item in enumerate(sparse_results):
        entry = fused.setdefault(
            item["id"], {"id": item["id"], "payload": item["payload"], "fused_score": 0.0,
                          "dense_rank": None, "sparse_rank": None}
        )
        entry["fused_score"] += sparse_weight * (1.0 / (k + rank + 1))
        entry["sparse_rank"] = rank + 1

    return sorted(fused.values(), key=lambda e: e["fused_score"], reverse=True)


def merge_candidate_pools(pools: list[list[dict]]) -> list[dict]:
    """Union several already-fused candidate pools into one.

    Used by multi-query retrieval (``QUERY_TRANSFORM=expand``): every rephrasing
    gets its own dense+sparse pass, and a chunk that several rephrasings agree on
    accumulates score (consensus), while a chunk only one phrasing found keeps
    its own. Scores from different pools are on the same RRF scale, so summing
    them is meaningful; ranks are not comparable across pools and are dropped.

    Returns entries sorted by fused_score descending, with ``variants`` recording
    how many queries surfaced the chunk.
    """
    merged: dict[str, dict] = {}
    for pool in pools:
        for entry in pool:
            current = merged.get(entry["id"])
            if current is None:
                merged[entry["id"]] = {**entry, "variants": 1}
                current = merged[entry["id"]]
            else:
                current["fused_score"] = current.get("fused_score", 0.0) + entry.get("fused_score", 0.0)
                current["variants"] = current.get("variants", 1) + 1
                # Keep the strongest evidence of either pass for downstream
                # confidence blending (dense cosine rides along from fusion).
                if entry.get("dense_score") is not None:
                    current["dense_score"] = max(
                        current.get("dense_score", float("-inf")), entry["dense_score"]
                    )
    return sorted(merged.values(), key=lambda e: e.get("fused_score", 0.0), reverse=True)
