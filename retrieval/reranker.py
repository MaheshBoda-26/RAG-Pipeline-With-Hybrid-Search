"""Second-pass reranking of the fused candidate pool.

Uses the chat model as an LLM-as-judge cross-encoder: given the actual
question and each candidate chunk, score relevance directly, rather than
relying on RRF's rank-based fusion of two different retrieval signals.
This is what turns "roughly the right neighborhood" into "the right chunk
is in the top 5." One batched call scores the whole candidate pool instead
of one call per chunk, to keep latency and cost down.
"""
from __future__ import annotations

import json

from openai import OpenAI

RERANK_SYSTEM_PROMPT = """You are a relevance-scoring assistant for a retrieval \
system. You will be given a user question and a numbered list of candidate \
text passages. Score each passage's relevance to answering the question on \
a 0-10 scale, where 10 means the passage directly and completely answers the \
question, and 0 means it is entirely unrelated.

Respond with ONLY a JSON array, one object per passage, in this exact form:
[{"index": 1, "score": 7}, {"index": 2, "score": 2}, ...]
Include every passage index exactly once. No prose, no markdown fences."""


def rerank(
    client: OpenAI,
    model: str,
    question: str,
    candidates: list[dict],
    top_n: int,
) -> list[dict]:
    """`candidates`: list of {id, payload, fused_score, ...} from fusion.py.
    Returns the top_n candidates re-sorted by LLM relevance score, each with
    a `rerank_score` field added."""
    if not candidates:
        return []

    passages_block = "\n\n".join(
        f"[{i+1}] {c['payload']['text']}" for i, c in enumerate(candidates)
    )
    user_prompt = f"Question: {question}\n\nCandidate passages:\n\n{passages_block}"

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": RERANK_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        scored = json.loads(raw)
        score_by_index = {int(item["index"]): float(item["score"]) for item in scored}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # Reranker returned something unparseable -- fail safe by falling back
        # to fusion order rather than crashing the whole request.
        score_by_index = {i + 1: c["fused_score"] for i, c in enumerate(candidates)}

    for i, c in enumerate(candidates):
        c["rerank_score"] = score_by_index.get(i + 1, 0.0)

    ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_n]
