"""Tests for content-hash incremental ingestion."""
from __future__ import annotations

from dataclasses import dataclass

from ingestion.incremental import document_hash, plan_incremental, stored_hashes


@dataclass
class _Doc:
    source: str
    text: str


def test_document_hash_is_stable_and_content_sensitive():
    assert document_hash("hello") == document_hash("hello")
    assert document_hash("hello") != document_hash("hello ")
    assert len(document_hash("x")) == 32


def test_document_hash_handles_empty_text():
    assert document_hash("") == document_hash("")


def test_stored_hashes_ignores_records_without_hash():
    chunks = [
        {"payload": {"source": "a.md", "doc_hash": "h1"}},
        {"payload": {"source": "b.md"}},
        {"payload": {}},
        {"payload": {"source": "c.md", "doc_hash": "h2"}},
    ]

    assert stored_hashes(chunks) == {"a.md": "h1", "c.md": "h2"}


def test_plan_skips_unchanged_documents():
    doc = _Doc("a.md", "same text")
    stored = {"a.md": document_hash("same text")}

    changed, unchanged = plan_incremental([doc], stored)

    assert changed == []
    assert unchanged == ["a.md"]


def test_plan_reprocesses_changed_and_new_documents():
    edited = _Doc("a.md", "edited text")
    added = _Doc("b.md", "brand new")
    stored = {"a.md": document_hash("old text")}

    changed, unchanged = plan_incremental([edited, added], stored)

    assert [doc.source for doc in changed] == ["a.md", "b.md"]
    assert unchanged == []


def test_plan_treats_missing_hash_as_changed():
    """An index built before hashes existed must re-ingest, not go stale."""
    doc = _Doc("a.md", "text")

    changed, unchanged = plan_incremental([doc], {})

    assert changed == [doc]
    assert unchanged == []
