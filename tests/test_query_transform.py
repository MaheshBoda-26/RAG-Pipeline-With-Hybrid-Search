"""Tests for QUERY_TRANSFORM (none | rewrite | expand)."""
from __future__ import annotations

from retrieval.query_transform import dedupe, normalize_query, transform_queries


class _Message:
    def __init__(self, content):
        self.content = content


class _Completions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = 0
        self.last_messages = None

    def create(self, **kwargs):
        self.calls += 1
        self.last_messages = kwargs.get("messages")
        if self.error:
            raise self.error
        return type("R", (), {"choices": [type("C", (), {"message": _Message(self.content)})()]})()


def stub_client(content=None, error=None):
    completions = _Completions(content, error)
    client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})
    return client, completions


def test_none_mode_returns_the_original_question_only():
    assert transform_queries("what is the retry limit?", "none") == ["what is the retry limit?"]


def test_unknown_mode_falls_back_to_the_original_question():
    assert transform_queries("q about limits", "banana") == ["q about limits"]


def test_no_client_means_no_transformation():
    """A missing client must not silently drop the question."""
    assert transform_queries("original", "expand", client=None) == ["original"]


def test_rewrite_replaces_the_question_when_the_model_returns_a_query():
    client, _ = stub_client("API retry limit and backoff behavior")
    result = transform_queries("what happens when it fails?", "rewrite", client, "model")
    assert result == ["API retry limit and backoff behavior"]


def test_rewrite_falls_back_when_the_model_answers_instead_of_rewriting():
    client, _ = stub_client("Sure! Here is a rewritten query: retry limits")
    assert transform_queries("limits?", "rewrite", client, "model") == ["limits?"]


def test_rewrite_falls_back_when_the_api_errors():
    client, _ = stub_client(error=RuntimeError("timeout"))
    assert transform_queries("limits?", "rewrite", client, "model") == ["limits?"]


def test_rewrite_falls_back_when_output_is_identical():
    client, _ = stub_client("limits?")
    assert transform_queries("limits?", "rewrite", client, "model") == ["limits?"]


def test_expand_keeps_the_original_first_and_caps_the_variants():
    client, _ = stub_client('["retry limit", "backoff schedule", "request timeout", "fourth variant"]')

    result = transform_queries("limits?", "expand", client, "model", variants=3)

    assert result[0] == "limits?"
    assert len(result) == 3
    assert "fourth variant" not in result


def test_expand_dedupes_case_insensitively():
    client, _ = stub_client('["LIMITS?", "retry limit"]')

    result = transform_queries("limits?", "expand", client, "model", variants=3)

    assert result == ["limits?", "retry limit"]


def test_expand_ignores_unparseable_output():
    client, _ = stub_client("- retry limit\n- backoff")
    assert transform_queries("limits?", "expand", client, "model") == ["limits?"]


def test_normalize_query_rejects_blank_and_oversized_output():
    assert normalize_query("") is None
    assert normalize_query("  hi  ") is None
    assert normalize_query("x" * 400) is None


def test_normalize_query_strips_numbering_quotes_and_leading_lines():
    assert normalize_query('1. "retry limit"') == "retry limit"
    assert normalize_query("Here is the query\nretry limit") is None  # anchored prefix rejection


def test_dedupe_preserves_first_occurrence_order():
    assert dedupe(["a", "B", "A", "b", "c"]) == ["a", "B", "c"]
