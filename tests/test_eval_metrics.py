"""Unit tests for retrieval-quality metrics (no API calls, fully deterministic)."""
from __future__ import annotations

import math

import pytest

from tests.eval.metrics import (
    aggregate,
    first_relevant_rank,
    is_relevant,
    mrr,
    ndcg_at_k,
    normalize,
    recall_at_k,
    relevance_flags,
)

GOLDEN = "Requests without a valid key return 401 Unauthorized."


def test_normalize_strips_punctuation_and_case():
    assert normalize("  Hello,   WORLD! ") == "hello world"


def test_is_relevant_matches_containment():
    assert is_relevant("Docs say: Requests without a valid key return 401 Unauthorized.", GOLDEN)


def test_is_relevant_matches_partial_chunk_body():
    chunk = "Requests without a valid key return 401 Unauthorized. See the auth guide."
    assert is_relevant(chunk, GOLDEN)


def test_is_relevant_rejects_unrelated_text():
    assert not is_relevant("Kubernetes deployment requires Helm charts.", GOLDEN)


def test_is_relevant_requires_a_non_empty_context():
    assert not is_relevant("anything", "")


def test_relevance_flags_follow_rank_order():
    sources = [
        {"text": "Unrelated deployment notes."},
        {"text": "Requests without a valid key return 401 Unauthorized."},
    ]
    assert relevance_flags(sources, GOLDEN) == [False, True]


def test_first_relevant_rank_and_mrr():
    flags = [False, False, True, True]
    assert first_relevant_rank(flags) == 3
    assert mrr(flags) == pytest.approx(1 / 3)
    assert mrr([False, False]) == 0.0
    assert first_relevant_rank([False]) is None


def test_recall_at_k_counts_only_the_top_k():
    flags = [False, False, True]
    assert recall_at_k(flags, 1) == 0.0
    assert recall_at_k(flags, 3) == 1.0
    assert recall_at_k([], 5) == 0.0


def test_ndcg_at_k_discounts_by_rank():
    assert ndcg_at_k([True], 5) == pytest.approx(1.0)
    assert ndcg_at_k([False, True], 5) == pytest.approx(1 / math.log2(3))
    assert ndcg_at_k([False, True], 1) == 0.0
    assert ndcg_at_k([False, False, False], 5) == 0.0


def test_aggregate_averages_across_queries():
    summary = aggregate([[True], [False, True], [False, False]])

    assert summary["queries"] == 3
    assert summary["recall_at_1"] == pytest.approx(1 / 3)
    assert summary["recall_at_3"] == pytest.approx(2 / 3)
    assert summary["mrr"] == pytest.approx((1 + 0.5 + 0) / 3)


def test_aggregate_handles_no_queries():
    summary = aggregate([])

    assert summary["queries"] == 0
    assert summary["mrr"] is None
    assert summary["recall_at_5"] is None
