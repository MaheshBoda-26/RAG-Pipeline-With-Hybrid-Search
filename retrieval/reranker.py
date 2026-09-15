"""Second-pass reranking of the fused candidate pool.

Uses a cross-encoder model (sentence-transformers) for fast local reranking,
replacing the previous LLM-as-judge approach. Falls back to fusion scores
if cross-encoder is unavailable or fails.
"""
from __future__ import annotations

from retrieval.cross_encoder_reranker import rerank as cross_encoder_rerank
from config import Settings


def rerank(
    client,  # kept for backward compatibility but unused
    model: str,  # kept for backward compatibility but unused
    question: str,
    candidates: list[dict],
    top_n: int,
    settings: Settings | None = None,
) -> list[dict]:
    """Rerank candidates using cross-encoder.

    `candidates`: list of {id, payload, fused_score, ...} from fusion.py.
    Returns the top_n candidates re-sorted by cross-encoder relevance score,
    each with a `rerank_score` field added (0-10 scale).
    """
    # Use cross-encoder reranker with settings if provided, otherwise defaults
    if settings:
        return cross_encoder_rerank(
            question, candidates, top_n,
            model_name=settings.cross_encoder_model,
            device=settings.cross_encoder_device,
            max_length=settings.cross_encoder_max_length,
        )
    # Backward compatibility: use defaults
    return cross_encoder_rerank(question, candidates, top_n)