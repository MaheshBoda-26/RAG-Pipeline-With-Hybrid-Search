"""Second-pass reranking of the fused candidate pool.

Two interchangeable strategies, selected by ``RERANK_MODE``:

- ``cross-encoder`` (default): a local ms-marco cross-encoder, ~100 ms for a
  15-candidate pool on CPU, no API cost, scores calibrated by the model's own
  sigmoid so a weak passage scores low no matter what else was retrieved.
- ``llm``: an LLM judge, one call per question. Slower and metered, useful when
  the corpus vocabulary is far from the cross-encoder's training distribution.

Both paths emit ``rerank_score`` on the same 0-10 scale and fall back to
neutral fusion scores (capped at 5.0) when they cannot score, so the confidence
gate downstream behaves identically either way.
"""
from __future__ import annotations

from config import Settings
from retrieval.llm_reranker import llm_rerank
from retrieval.cross_encoder_reranker import rerank as cross_encoder_rerank


def rerank(
    client,  # used only by RERANK_MODE=llm; kept positional for compatibility
    model: str,  # used only by RERANK_MODE=llm
    question: str,
    candidates: list[dict],
    top_n: int,
    settings: Settings | None = None,
) -> list[dict]:
    """Rerank candidates and return the top_n.

    `candidates`: list of {id, payload, fused_score, ...} from fusion.
    Each returned candidate carries `rerank_score` (0-10) and `rerank_mode`.
    """
    mode = settings.normalized_rerank_mode if settings else "cross-encoder"

    if mode == "llm":
        return llm_rerank(client, model, question, candidates, top_n)

    if settings:
        ranked = cross_encoder_rerank(
            question, candidates, top_n,
            model_name=settings.cross_encoder_model,
            device=settings.cross_encoder_device,
            max_length=settings.cross_encoder_max_length,
        )
    else:
        ranked = cross_encoder_rerank(question, candidates, top_n)

    for candidate in ranked:
        candidate.setdefault("rerank_mode", "cross-encoder")
    return ranked
