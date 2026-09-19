"""Retrieval-quality metrics for the golden set.

Ground truth is the golden item's ``context`` field: the passage that contains
the answer. A retrieved chunk counts as relevant when it carries that passage,
so the metrics here answer exactly one question per query:

    did the pipeline actually retrieve the passage that holds the answer?

That separates *retrieval* failures from *generation* failures, which is the
whole point of evaluating the two halves independently.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE = re.compile(r"\s+")

# Chunks occasionally trim the tail of a golden passage; token overlap below
# this ratio means the chunk is a different passage, not a truncated match.
MIN_TOKEN_OVERLAP = 0.7


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return _WHITESPACE.sub(" ", _PUNCT.sub(" ", (text or "").lower())).strip()


def is_relevant(retrieved_text: str, expected_context: str) -> bool:
    """True when ``retrieved_text`` carries the golden passage."""
    got, want = normalize(retrieved_text), normalize(expected_context)
    if not want or not got:
        return False

    # Primary test: the golden passage survives chunking inside the retrieved text.
    if want in got:
        return True
    # Chunkers may trim the passage; a near-complete overlap still counts.
    want_tokens = set(want.split())
    got_tokens = set(got.split())
    if not want_tokens:
        return False
    return len(want_tokens & got_tokens) / len(want_tokens) >= MIN_TOKEN_OVERLAP


def relevance_flags(sources: Sequence[dict], expected_context: str) -> list[bool]:
    """Relevance of each retrieved source, in rank order."""
    return [is_relevant(source.get("text", ""), expected_context) for source in sources]


def first_relevant_rank(flags: Sequence[bool]) -> int | None:
    """1-based rank of the first relevant source, or None."""
    for rank, hit in enumerate(flags, start=1):
        if hit:
            return rank
    return None


def recall_at_k(flags: Sequence[bool], k: int) -> float:
    """1.0 when any of the top-k sources is relevant."""
    return 1.0 if any(flags[:k]) else 0.0


def mrr(flags: Sequence[bool]) -> float:
    """Reciprocal rank of the first relevant source (0.0 when none)."""
    rank = first_relevant_rank(flags)
    return 1.0 / rank if rank else 0.0


def ndcg_at_k(flags: Sequence[bool], k: int) -> float:
    """Binary-gain NDCG@k (one relevant passage per query, so IDCG = 1)."""
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, hit in enumerate(flags[:k], start=1)
        if hit
    )
    return dcg


def aggregate(
    per_query_flags: Iterable[Sequence[bool]],
    k_values: Sequence[int] = (1, 3, 5),
) -> dict[str, float | int | None]:
    """Mean metrics across queries."""
    flags_list = [list(flags) for flags in per_query_flags]
    if not flags_list:
        empty: dict[str, float | int | None] = {f"recall_at_{k}": None for k in k_values}
        empty.update({"mrr": None, "ndcg_at_5": None, "queries": 0})
        return empty

    total = len(flags_list)
    summary: dict[str, float | int | None] = {
        f"recall_at_{k}": sum(recall_at_k(flags, k) for flags in flags_list) / total
        for k in k_values
    }
    summary["mrr"] = sum(mrr(flags) for flags in flags_list) / total
    summary["ndcg_at_5"] = sum(ndcg_at_k(flags, 5) for flags in flags_list) / total
    summary["queries"] = total
    return summary
