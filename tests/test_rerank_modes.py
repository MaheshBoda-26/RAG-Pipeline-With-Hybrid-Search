"""Tests for RERANK_MODE dispatch, config validation, and multi-query merging."""
from __future__ import annotations

from config import Settings
from retrieval.fusion import merge_candidate_pools
from retrieval.reranker import rerank


def make_candidates() -> list[dict]:
    return [
        {"id": "a", "payload": {"text": "alpha"}, "fused_score": 0.02, "dense_score": 0.5},
        {"id": "b", "payload": {"text": "beta"}, "fused_score": 0.01, "dense_score": 0.4},
    ]


class _JudgeClient:
    """Client that always returns a judge verdict."""

    def __init__(self, content):
        self.calls = 0
        self._content = content
        completions = self

        def create(**kwargs):
            self.calls += 1
            message = type("M", (), {"content": self._content})()
            choice = type("C", (), {"message": message})()
            return type("R", (), {"choices": [choice]})()

        self.create = create

    @property
    def chat(self):
        return type("Chat", (), {"completions": self})()


def test_default_mode_is_cross_encoder(monkeypatch):
    monkeypatch.delenv("RERANK_MODE", raising=False)

    assert Settings().normalized_rerank_mode == "cross-encoder"


def test_unknown_mode_normalizes_to_cross_encoder(monkeypatch):
    monkeypatch.setenv("RERANK_MODE", "magic")
    settings = Settings()

    assert settings.normalized_rerank_mode == "cross-encoder"


def test_llm_mode_is_honored(monkeypatch):
    monkeypatch.setenv("RERANK_MODE", "llm")

    assert Settings().normalized_rerank_mode == "llm"


def test_query_transform_defaults_to_none_and_validates(monkeypatch):
    monkeypatch.delenv("QUERY_TRANSFORM", raising=False)
    assert Settings().normalized_query_transform == "none"

    monkeypatch.setenv("QUERY_TRANSFORM", "rewrite")
    assert Settings().normalized_query_transform == "rewrite"

    monkeypatch.setenv("QUERY_TRANSFORM", "banana")
    assert Settings().normalized_query_transform == "none"


def test_contextual_retrieval_is_off_by_default(monkeypatch):
    monkeypatch.delenv("CONTEXTUAL_RETRIEVAL", raising=False)

    settings = Settings()

    assert settings.contextual_retrieval is False
    assert settings.contextual_model == settings.chat_model


def test_rerank_dispatches_to_llm_judge(monkeypatch):
    monkeypatch.setenv("RERANK_MODE", "llm")
    settings = Settings()
    client = _JudgeClient('[{"id": 1, "score": 2}, {"id": 2, "score": 9}]')

    ranked = rerank(client, settings.chat_model, "question", make_candidates(), 1, settings)

    assert client.calls == 1
    assert [c["id"] for c in ranked] == ["b"]
    assert ranked[0]["rerank_mode"] == "llm"


def test_rerank_default_mode_never_calls_the_judge(monkeypatch):
    """The default path must stay local: no API call, no per-query cost."""
    monkeypatch.delenv("RERANK_MODE", raising=False)
    settings = Settings()
    client = _JudgeClient('[{"id": 1, "score": 10}]')

    ranked = rerank(client, settings.chat_model, "question", make_candidates(), 2, settings)

    assert client.calls == 0
    assert all(c["rerank_mode"] == "cross-encoder" for c in ranked)


def test_merge_candidate_pools_boosts_consensus_hits():
    pool_a = [{"id": "a", "payload": {"text": "a"}, "fused_score": 0.02, "dense_score": 0.5}]
    pool_b = [
        {"id": "a", "payload": {"text": "a"}, "fused_score": 0.02, "dense_score": 0.6},
        {"id": "b", "payload": {"text": "b"}, "fused_score": 0.03},
    ]

    merged = merge_candidate_pools([pool_a, pool_b])

    assert [entry["id"] for entry in merged] == ["a", "b"]
    assert merged[0]["fused_score"] == 0.04  # seen by both queries
    assert merged[0]["variants"] == 2
    assert merged[0]["dense_score"] == 0.6  # strongest evidence kept
    assert merged[1]["variants"] == 1


def test_merge_candidate_pools_handles_a_single_pool():
    pool = make_candidates()

    assert [entry["id"] for entry in merge_candidate_pools([pool])] == ["a", "b"]


def test_merge_candidate_pools_handles_empty_input():
    assert merge_candidate_pools([]) == []
    assert merge_candidate_pools([[], []]) == []
