"""Contextual retrieval — opt-in via ``CONTEXTUAL_RETRIEVAL=true``.

A chunk embedded on its own loses the context it had in its document: a
paragraph that says "the default is 30 seconds" is nearly unfindable, because
neither the entity nor the unit is in the chunk. Contextual retrieval fixes the
*input* rather than the search: before embedding, a model writes one or two
sentences that situate the chunk inside its document, and that text is prepended
to the chunk for both the embedding and the keyword index. The original passage
is still what gets shown to the user and what citations resolve to.

The generated contexts are cached on disk keyed by (document hash, chunk text),
so re-ingesting an unchanged corpus costs no model calls, and a cache miss on a
changed chunk regenerates only that chunk.

Everything here is best-effort: if the model call fails, or the response looks
like an attempt to answer rather than situate, the chunk is left exactly as it
was. Ingest must never fail because an optional enhancement broke.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from collections.abc import Callable

logger = logging.getLogger(__name__)

MAX_DOCUMENT_CHARS = 6000
MAX_CONTEXT_CHARS = 400

SITUATE_PROMPT = """You situate a chunk inside its source document for a search index.

Write 1-2 short sentences that place the chunk in context: what document it is
from, what section or topic it belongs to, and what entity the details in it
refer to (name the product, API, config key or system the chunk is about).

Rules:
- Use only facts present in the document below. Never invent details.
- Do not answer questions, do not summarize the whole document, do not use the
  word "chunk", and do not start with "This chunk...".
- Output only the context sentences, with no preamble."""


def chunk_key(document_hash: str, chunk_text: str) -> str:
    """Cache key for one chunk: stable across runs, sensitive to edits."""
    digest = hashlib.sha256(f"{document_hash}\x00{chunk_text}".encode()).hexdigest()
    return digest[:32]


class ContextCache:
    """Small JSON-backed cache. A corrupt file is ignored, never fatal."""

    def __init__(self, path: str | os.PathLike[str] = "./.context_cache.json"):
        self.path = Path(path)
        self.entries: dict[str, str] = {}
        self.hits = 0
        self.misses = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            if isinstance(data, dict):
                self.entries = {str(k): str(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError):
            logger.warning("Ignoring unreadable context cache at %s", self.path)

    def get(self, key: str) -> str | None:
        value = self.entries.get(key)
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
        return value

    def set(self, key: str, value: str) -> None:
        self.entries[key] = value

    def save(self) -> None:
        if not self.entries:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(json.dumps(self.entries, indent=0, sort_keys=True))
            temp.replace(self.path)
        except OSError as exc:
            logger.warning("Could not persist context cache to %s: %s", self.path, exc)


def clean_context(raw: str) -> str | None:
    """Accept a generated context only if it reads like one."""
    if not raw:
        return None
    text = " ".join(raw.strip().split())
    text = text.strip("\"'` ")
    if not 20 <= len(text) <= MAX_CONTEXT_CHARS:
        return None
    lowered = text.lower()
    if lowered.startswith(("chunk", "this chunk", "here is", "sure,", "the answer")):
        return None
    if "\n" in raw.strip():
        # Multi-paragraph output means the model started doing something else.
        return None
    return text


def make_llm_generator(client, model: str) -> Callable[[str], str]:
    """Adapt a chat client into the ``prompt -> text`` callable the ingest uses."""

    def generate(prompt: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SITUATE_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return response.choices[0].message.content or ""

    return generate


def situate_prompt(document_text: str, chunk_text: str) -> str:
    document = document_text[:MAX_DOCUMENT_CHARS]
    return f"<document>\n{document}\n</document>\n\n<chunk>\n{chunk_text}\n</chunk>"


def add_chunk_contexts(
    chunks: list,
    document_text: str,
    document_hash: str,
    generate: Callable[[str], str],
    cache: ContextCache | None = None,
    max_chunks: int = 400,
) -> int:
    """Attach ``chunk.context`` to every chunk, using the cache where possible.

    Args:
        chunks: objects with ``context`` and ``text`` attributes (``Chunk``).
        document_text: full document text, for situating each chunk.
        document_hash: content hash of the document (cache namespace).
        generate: ``prompt -> text`` model callable.
        cache: optional persistent cache.
        max_chunks: hard cap on *uncached* generations per call, so a huge
            document cannot silently turn into thousands of model calls.

    Returns the number of chunks that were newly generated (cache hits excluded).
    """
    generated = 0
    for chunk in chunks:
        if getattr(chunk, "context", None):
            continue

        key = chunk_key(document_hash, chunk.text)
        cached = cache.get(key) if cache else None
        if cached:
            chunk.context = cached
            continue

        if generated >= max_chunks:
            logger.warning(
                "Contextual retrieval cap (%d chunks) reached for this document; "
                "remaining chunks are indexed without situating context.",
                max_chunks,
            )
            break

        try:
            context = clean_context(generate(situate_prompt(document_text, chunk.text)))
        except Exception as exc:
            logger.warning("Context generation failed, indexing chunk as-is: %s", exc)
            break

        if not context:
            # A rejected response is a signal about the model/prompt, not about
            # this chunk — stop calling rather than burning the whole document.
            logger.warning("Context generation returned unusable output; stopping for this document.")
            break

        chunk.context = context
        generated += 1
        if cache:
            cache.set(key, context)

    if cache:
        cache.save()
    return generated
