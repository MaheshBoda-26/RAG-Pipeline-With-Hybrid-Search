"""LLM-as-judge reranker — opt-in via ``RERANK_MODE=llm``.

The default reranker is a local cross-encoder (fast, calibrated, no API cost).
This module keeps the LLM-as-judge path available as a documented alternative
for corpora where a cross-encoder trained on web search passages underperforms:
the judge sees the question and each candidate passage and returns relevance on
the same 0-10 scale the cross-encoder produces, so every downstream consumer
(retrieval confidence, refusal gate, UI) stays identical.

Failure mode mirrors the cross-encoder: if the judge call fails or its output
cannot be parsed, candidates keep their fusion order with scores capped at 5.0
(neutral). Fusion rank carries no absolute relevance signal, so claiming more
than neutral would let the pipeline bypass its own refusal gate.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# Fusion-fallback ceiling. See cross_encoder_reranker.rerank for the rationale.
FUSION_FALLBACK_CAP = 5.0
FUSION_SCORE_SCALE = 400.0

MAX_PASSAGE_CHARS = 1200

JUDGE_PROMPT = """You are a relevance judge for a retrieval system.

For each numbered passage, score how well it answers the QUESTION, from 0 to 10:
- 10 = passage directly and completely answers the question
- 7-9 = passage contains the answer or the essential evidence for it
- 4-6 = passage is topically related but does not answer the question
- 1-3 = passage is barely related
- 0 = passage is irrelevant

Judge only what is written in the passage. Do not reward plausible-sounding text.
Respond with ONLY a JSON array, one object per passage, in order:
[{"id": 1, "score": 8}, {"id": 2, "score": 2}]"""

_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


def build_prompt(question: str, candidates: list[dict]) -> str:
    """Numbered passage block for the judge."""
    blocks = []
    for index, candidate in enumerate(candidates, start=1):
        text = (candidate.get("payload") or {}).get("text", "")[:MAX_PASSAGE_CHARS]
        blocks.append(f"[{index}] {text}")
    return f"QUESTION: {question}\n\nPASSAGES:\n" + "\n\n".join(blocks)


def parse_scores(raw: str, expected: int) -> list[float] | None:
    """Parse the judge response into one score per candidate, in order.

    Returns ``None`` when the response cannot be trusted: a missing passage, a
    duplicate id, a non-numeric score, or an out-of-range score. A partial parse
    is worse than no parse — misaligned scores silently corrupt the ranking.
    """
    if not raw:
        return None

    match = _JSON_ARRAY.search(raw)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None

    by_id: dict[int, float] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            return None
        try:
            entry_id = int(entry["id"])
            score = float(entry["score"])
        except (KeyError, TypeError, ValueError):
            return None
        if entry_id in by_id or not 0.0 <= score <= 10.0:
            return None
        by_id[entry_id] = score

    if sorted(by_id) != list(range(1, expected + 1)):
        return None
    return [by_id[i] for i in range(1, expected + 1)]


def llm_rerank(
    client,
    model: str,
    question: str,
    candidates: list[dict],
    top_n: int,
) -> list[dict]:
    """Rerank ``candidates`` with an LLM judge, returning the top ``top_n``.

    Adds ``rerank_score`` (0-10) and ``rerank_mode`` to every candidate.
    """
    if not candidates:
        return []

    scores: list[float] | None = None
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": build_prompt(question, candidates)},
            ],
            temperature=0,
        )
        scores = parse_scores(response.choices[0].message.content or "", len(candidates))
    except Exception as exc:  # network, auth, rate limit, malformed response
        logger.warning("LLM reranker failed, falling back to fusion order: %s", exc)

    if scores is None:
        for candidate in candidates:
            candidate["rerank_score"] = min(
                FUSION_FALLBACK_CAP, candidate.get("fused_score", 0.0) * FUSION_SCORE_SCALE
            )
            candidate["rerank_mode"] = "llm_fallback"
    else:
        for candidate, score in zip(candidates, scores, strict=False):
            candidate["rerank_score"] = round(score, 4)
            candidate["rerank_mode"] = "llm"

    ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_n]
