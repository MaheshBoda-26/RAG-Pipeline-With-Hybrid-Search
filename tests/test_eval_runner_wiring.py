"""Offline coverage for the eval runner: retrieval metrics, no API calls.

A stub pipeline and a stub judge client drive the real ``run_evaluation`` loop,
so the metric wiring is verified deterministically in CI.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from config import Settings
from pipeline import AskResponse
from tests.eval.runner import run_evaluation

GOLDEN = [
    {
        "question": "What happens when you make a request without a valid API key?",
        "expected_answer": "The request is rejected with 401 Unauthorized.",
        "context": "Requests without a valid key return 401 Unauthorized.",
    }
]


class _StubCompletions:
    def create(self, model, messages, temperature=0):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"score": 0.9, "reasoning": "stub"}')
                )
            ]
        )


class _StubPipeline:
    """Pipeline whose second source holds the golden passage."""

    def __init__(self, sources: list[dict]):
        self.client = SimpleNamespace(chat=SimpleNamespace(completions=_StubCompletions()))
        self._sources = sources

    def ask(self, question: str, source: str | None = None) -> AskResponse:
        return AskResponse(
            question=question,
            answer="Requests without a valid key are rejected [2].",
            sources=self._sources,
            confidence={
                "retrieval_confidence": 0.9,
                "citation_coverage": 1.0,
                "completeness": 1.0,
                "composite": 0.9,
            },
            refused=False,
        )


def _source(block: int, text: str) -> dict:
    return {
        "block": block,
        "source": "authentication.md",
        "section_heading": None,
        "text": text,
        "fused_score": 1.0,
        "rerank_score": 1.0,
        "dense_score": 1.0,
    }


def test_run_evaluation_reports_rank_aware_retrieval_metrics():
    pipeline = _StubPipeline(
        [
            _source(1, "Kubernetes deployment requires Helm charts and ingress configuration."),
            _source(2, "Requests without a valid key return 401 Unauthorized."),
        ]
    )

    results, summary = run_evaluation(pipeline, GOLDEN, Settings())

    assert results[0].retrieved_flags == [False, True]
    assert results[0].relevant_rank == 2
    assert summary.recall_at_1 == 0.0
    assert summary.recall_at_3 == 1.0
    assert summary.recall_at_5 == 1.0
    assert summary.mrr == pytest.approx(0.5)
    assert summary.ndcg_at_5 == pytest.approx(1 / math.log2(3))


def test_run_evaluation_reports_zero_when_passage_is_missing():
    pipeline = _StubPipeline([_source(1, "Unrelated deployment notes.")])

    _, summary = run_evaluation(pipeline, GOLDEN, Settings())

    assert summary.recall_at_1 == 0.0
    assert summary.mrr == 0.0
    assert summary.ndcg_at_5 == 0.0
