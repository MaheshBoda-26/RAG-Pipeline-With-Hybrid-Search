"""Content-hash based incremental ingestion.

Re-ingesting a corpus should not re-embed documents that have not changed. Each
document's text is hashed, the hash is stored in the chunk payload, and a later
ingest compares against it: unchanged documents are skipped, changed ones are
re-processed.

The failure mode is deliberately safe — a document with no stored hash is
treated as changed, so an index built before this existed simply re-ingests
rather than silently going stale.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from typing import Protocol


class HasSourceAndText(Protocol):
    source: str
    text: str


def document_hash(text: str) -> str:
    """Stable content hash for a document body."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:32]


def stored_hashes(records: Iterable[dict]) -> dict[str, str]:
    """Map ``source -> doc_hash`` from stored chunk payloads.

    Records without a hash are ignored, which makes them look changed and
    therefore get re-processed.
    """
    hashes: dict[str, str] = {}
    for record in records:
        payload = record.get("payload") or {}
        source, digest = payload.get("source"), payload.get("doc_hash")
        if source and digest:
            hashes[source] = digest
    return hashes


def plan_incremental(
    documents: Sequence[HasSourceAndText],
    stored: dict[str, str],
) -> tuple[list[HasSourceAndText], list[str]]:
    """Split documents into (changed, unchanged-source-names).

    A document is unchanged only when its content hash matches what was indexed
    for the same source.
    """
    changed: list[HasSourceAndText] = []
    unchanged: list[str] = []
    for document in documents:
        if stored.get(document.source) == document_hash(document.text):
            unchanged.append(document.source)
        else:
            changed.append(document)
    return changed, unchanged
