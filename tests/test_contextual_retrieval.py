"""Tests for contextual retrieval (CONTEXTUAL_RETRIEVAL=true)."""
from __future__ import annotations

from ingestion.chunking import Chunk
from retrieval.contextual import (
    ContextCache,
    add_chunk_contexts,
    chunk_key,
    clean_context,
)


def make_chunk(text: str, index: int = 0) -> Chunk:
    return Chunk(
        id=f"c{index}",
        text=text,
        source="doc.txt",
        chunk_index=index,
        strategy="recursive",
        char_count=len(text),
    )


def test_clean_context_accepts_a_short_situating_sentence():
    assert clean_context("From the Aegis rate-limit guide, describing the retry budget.") == (
        "From the Aegis rate-limit guide, describing the retry budget."
    )


def test_clean_context_rejects_answers_and_meta_preamble():
    assert clean_context("This chunk is about retries, and it clearly explains the limit.") is None
    assert clean_context("Here is the context: rate limits apply.") is None
    assert clean_context("The answer is 30 seconds.") is None


def test_clean_context_rejects_too_short_and_too_long():
    assert clean_context("Retries.") is None
    assert clean_context("x" * 500) is None


def test_clean_context_rejects_multiline_output():
    assert clean_context("First sentence about retries.\nSecond paragraph entirely.") is None


def test_clean_context_tolerates_empty_input():
    assert clean_context("") is None


def test_chunk_key_is_stable_and_edit_sensitive():
    assert chunk_key("hash", "text") == chunk_key("hash", "text")
    assert chunk_key("hash", "text") != chunk_key("hash", "text ")
    assert chunk_key("hash", "text") != chunk_key("other", "text")


def test_add_chunk_contexts_uses_cache_on_second_pass(tmp_path):
    chunks = [make_chunk("retry limit is 3 attempts")]
    cache_path = tmp_path / "ctx.json"
    calls = []

    def generate(prompt):
        calls.append(prompt)
        return "From the Aegis API guide, describing the retry limit for failed requests."

    first = add_chunk_contexts(chunks, "doc body", "hash1", generate, ContextCache(cache_path))
    assert first == 1
    assert chunks[0].context.startswith("From the Aegis API guide")
    assert chunks[0].embedding_text.startswith("From the Aegis API guide")
    assert chunks[0].text == "retry limit is 3 attempts"

    # Second pass: fresh cache object reading the same file, no model call.
    fresh = [make_chunk("retry limit is 3 attempts")]
    cached_cache = ContextCache(cache_path)
    second = add_chunk_contexts(fresh, "doc body", "hash1", generate, cached_cache)

    assert second == 0
    assert cached_cache.hits == 1
    assert len(calls) == 1
    assert fresh[0].context == chunks[0].context


def test_add_chunk_contexts_stops_after_a_rejected_response():
    """A model that refuses to situate must not be called once per chunk."""
    chunks = [make_chunk(f"passage {i}", i) for i in range(5)]
    calls = []

    def generate(prompt):
        calls.append(prompt)
        return "This chunk explains retries."

    generated = add_chunk_contexts(chunks, "doc", "hash", generate)

    assert generated == 0
    assert len(calls) == 1
    assert all(chunk.context is None for chunk in chunks)


def test_add_chunk_contexts_respects_the_cap():
    chunks = [make_chunk(f"passage number {i}", i) for i in range(10)]

    def generate(prompt):
        return "From the Aegis API guide, describing the retry budget for failures."

    generated = add_chunk_contexts(chunks, "doc", "hash", generate, max_chunks=3)

    assert generated == 3
    assert sum(1 for c in chunks if c.context) == 3


def test_add_chunk_contexts_survives_a_failing_generator():
    chunks = [make_chunk("retry limit")]

    def generate(prompt):
        raise RuntimeError("api down")

    assert add_chunk_contexts(chunks, "doc", "hash", generate) == 0
    assert chunks[0].context is None
    assert chunks[0].embedding_text == "retry limit"


def test_add_chunk_contexts_keeps_existing_contexts():
    chunk = make_chunk("retry limit")
    chunk.context = "Pre-existing situating context from a previous run."
    calls = []

    add_chunk_contexts([chunk], "doc", "hash", lambda p: calls.append(p) or "ignored text here")

    assert calls == []
    assert chunk.context.startswith("Pre-existing")


def test_context_cache_ignores_a_corrupt_file(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json")

    cache = ContextCache(path)

    assert cache.entries == {}
