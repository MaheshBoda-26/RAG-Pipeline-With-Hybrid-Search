"""Tests for the opt-in LLM-as-judge reranker (RERANK_MODE=llm)."""
from __future__ import annotations

import pytest

from retrieval.llm_reranker import build_prompt, llm_rerank, parse_scores


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return _Response(self.content)


class StubClient:
    """Minimal stand-in for the OpenAI client."""

    def __init__(self, content=None, error=None):
        self.chat = type("Chat", (), {"completions": _Completions(content, error)})()


def _candidates(texts: list[str]) -> list[dict]:
    return [
        {"id": f"id{i}", "payload": {"text": text}, "fused_score": 0.01}
        for i, text in enumerate(texts)
    ]


def test_parse_scores_returns_one_score_per_candidate_in_order():
    raw = '[{"id": 2, "score": 9}, {"id": 1, "score": 3}]'

    assert parse_scores(raw, 2) == [3.0, 9.0]


def test_parse_scores_rejects_missing_candidate():
    """A partial parse would misalign scores with passages — reject it."""
    assert parse_scores('[{"id": 1, "score": 9}]', 2) is None


def test_parse_scores_rejects_duplicate_ids():
    assert parse_scores('[{"id": 1, "score": 9}, {"id": 1, "score": 2}]', 2) is None


def test_parse_scores_rejects_out_of_range_and_nonnumeric():
    assert parse_scores('[{"id": 1, "score": 42}]', 1) is None
    assert parse_scores('[{"id": 1, "score": "high"}]', 1) is None


def test_parse_scores_tolerates_code_fences_and_preamble():
    raw = 'Here you go:\n```json\n[{"id": 1, "score": 7}]\n```'

    assert parse_scores(raw, 1) == [7.0]


def test_llm_rerank_sorts_by_judge_score():
    client = StubClient('[{"id": 1, "score": 2}, {"id": 2, "score": 9}, {"id": 3, "score": 5}]')
    candidates = _candidates(["weak", "strong", "middling"])

    ranked = llm_rerank(client, "model", "question", candidates, top_n=2)

    assert [c["id"] for c in ranked] == ["id1", "id2"]
    assert ranked[0]["rerank_score"] == 9.0
    assert all(c["rerank_mode"] == "llm" for c in ranked)


def test_llm_rerank_falls_back_to_neutral_fusion_scores_on_api_error():
    client = StubClient(error=RuntimeError("boom"))
    candidates = _candidates(["a", "b"])
    candidates[0]["fused_score"] = 0.02
    candidates[1]["fused_score"] = 0.01

    ranked = llm_rerank(client, "model", "question", candidates, top_n=2)

    assert [c["id"] for c in ranked] == ["id0", "id1"]
    assert all(c["rerank_mode"] == "llm_fallback" for c in ranked)
    # Never above neutral: fusion rank carries no absolute relevance signal.
    assert all(c["rerank_score"] <= 5.0 for c in ranked)


def test_llm_rerank_falls_back_when_response_is_unparseable():
    client = StubClient("I think passage one is best.")
    candidates = _candidates(["a", "b"])

    ranked = llm_rerank(client, "model", "question", candidates, top_n=2)

    assert all(c["rerank_mode"] == "llm_fallback" for c in ranked)


def test_llm_rerank_returns_empty_without_candidates():
    client = StubClient("[]")

    assert llm_rerank(client, "model", "question", [], top_n=3) == []


def test_build_prompt_truncates_long_passages():
    """A 5k-char passage must not blow up the judge prompt."""
    prompt = build_prompt("question", _candidates(["x" * 5000]))

    assert len(prompt) < 2_000
    assert prompt.startswith("QUESTION: question")


def test_llm_rerank_accepts_json_array_of_objects_with_extra_keys():
    client = StubClient('[{"id": 1, "score": 6, "reason": "matches the API name"}]')

    ranked = llm_rerank(client, "model", "question", _candidates(["a"]), top_n=1)

    assert ranked[0]["rerank_score"] == 6.0


@pytest.mark.parametrize("raw", ["", "[]", "not json at all"])
def test_parse_scores_rejects_unusable_output(raw):
    assert parse_scores(raw, 1) is None
