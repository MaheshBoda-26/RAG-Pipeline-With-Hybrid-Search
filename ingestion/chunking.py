"""Three switchable chunking strategies, all producing the same Chunk shape
so downstream retrieval code never needs to know which one built a chunk.

- fixed:     naive sliding window over raw characters. Baseline.
- recursive: splits on markdown/section structure first, falling back to
             fixed-size splitting inside any section that's still too big.
             Structure-aware, cheap, no embedding calls.
- semantic:  splits sentence-by-sentence, growing a chunk while consecutive
             sentences stay topically similar (embedding cosine distance),
             cutting a new chunk when the topic drifts.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ingestion.loaders import RawDocument

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    chunk_index: int
    strategy: str
    char_count: int
    section_heading: str | None = None
    embedding: list[float] | None = field(default=None, repr=False)


def _make_chunk(text: str, source: str, index: int, strategy: str, heading: str | None) -> Chunk:
    return Chunk(
        id=str(uuid.uuid4()),
        text=text.strip(),
        source=source,
        chunk_index=index,
        strategy=strategy,
        char_count=len(text.strip()),
        section_heading=heading,
    )


# ---------------------------------------------------------------------------
# Strategy 1: fixed-size with overlap
# ---------------------------------------------------------------------------
def chunk_fixed(doc: RawDocument, size: int = 800, overlap: int = 120) -> list[Chunk]:
    text = doc.text
    chunks = []
    start = 0
    index = 0
    step = max(size - overlap, 1)
    while start < len(text):
        piece = text[start : start + size]
        if piece.strip():
            chunks.append(_make_chunk(piece, doc.source, index, "fixed", None))
            index += 1
        start += step
    return chunks


# ---------------------------------------------------------------------------
# Strategy 2: recursive / structure-aware
# ---------------------------------------------------------------------------
def _split_by_headings(text: str) -> list[tuple[str | None, str]]:
    """Split into (heading, section_text) pairs on markdown headings.
    If no headings are found, returns a single (None, text) section."""
    matches = list(MARKDOWN_HEADING_RE.finditer(text))
    if not matches:
        return [(None, text)]

    sections = []
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((heading, text[start:end]))
    # Anything before the first heading (e.g. a title/preamble) still matters.
    if matches[0].start() > 0:
        sections.insert(0, (None, text[: matches[0].start()]))
    return sections


def chunk_recursive(doc: RawDocument, max_size: int = 800, overlap: int = 120) -> list[Chunk]:
    sections = _split_by_headings(doc.text)
    chunks = []
    index = 0
    for heading, section_text in sections:
        section_text = section_text.strip()
        if not section_text:
            continue
        if len(section_text) <= max_size:
            chunks.append(_make_chunk(section_text, doc.source, index, "recursive", heading))
            index += 1
        else:
            # Section too big for one chunk: fall back to paragraph-first,
            # then fixed-size splitting within it, preserving the heading tag.
            paragraphs = [p for p in re.split(r"\n\s*\n", section_text) if p.strip()]
            buffer = ""
            for para in paragraphs:
                if len(buffer) + len(para) + 1 <= max_size:
                    buffer = f"{buffer}\n{para}" if buffer else para
                else:
                    if buffer:
                        chunks.append(_make_chunk(buffer, doc.source, index, "recursive", heading))
                        index += 1
                    if len(para) <= max_size:
                        buffer = para
                    else:
                        # Single paragraph still too large: hard-split it.
                        start = 0
                        step = max(max_size - overlap, 1)
                        while start < len(para):
                            piece = para[start : start + max_size]
                            chunks.append(
                                _make_chunk(piece, doc.source, index, "recursive", heading)
                            )
                            index += 1
                            start += step
                        buffer = ""
            if buffer:
                chunks.append(_make_chunk(buffer, doc.source, index, "recursive", heading))
                index += 1
    return chunks


# ---------------------------------------------------------------------------
# Strategy 3: semantic (embedding-similarity boundary detection)
# ---------------------------------------------------------------------------
def chunk_semantic(
    doc: RawDocument,
    embed_fn: Callable[[list[str]], list[list[float]]],
    similarity_threshold: float = 0.28,
    max_size: int = 1200,
) -> list[Chunk]:
    """Grow a chunk sentence-by-sentence while each new sentence stays close
    (cosine distance) to the running mean embedding of the current chunk.
    A large jump in topic starts a new chunk. `similarity_threshold` is a
    cosine *distance* cutoff (0 = identical, 2 = opposite) — smaller value
    means chunks split more eagerly."""
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(doc.text) if s.strip()]
    if not sentences:
        return []
    if len(sentences) == 1:
        return [_make_chunk(sentences[0], doc.source, 0, "semantic", None)]

    embeddings = np.array(embed_fn(sentences))
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-8
    unit = embeddings / norms

    chunks = []
    index = 0
    current_sentences = [sentences[0]]
    current_vec = unit[0]
    current_len = len(sentences[0])

    for i in range(1, len(sentences)):
        distance = 1 - float(np.dot(current_vec, unit[i]))
        would_exceed = current_len + len(sentences[i]) > max_size
        if distance > similarity_threshold or would_exceed:
            chunks.append(
                _make_chunk(" ".join(current_sentences), doc.source, index, "semantic", None)
            )
            index += 1
            current_sentences = [sentences[i]]
            current_vec = unit[i]
            current_len = len(sentences[i])
        else:
            current_sentences.append(sentences[i])
            # running mean embedding, re-normalized
            n = len(current_sentences)
            current_vec = (current_vec * (n - 1) + unit[i]) / n
            norm = np.linalg.norm(current_vec)
            if norm > 0:
                current_vec = current_vec / norm
            current_len += len(sentences[i])

    if current_sentences:
        chunks.append(_make_chunk(" ".join(current_sentences), doc.source, index, "semantic", None))
    return chunks


STRATEGIES = {
    "fixed": chunk_fixed,
    "recursive": chunk_recursive,
    "semantic": chunk_semantic,  # requires embed_fn — called differently, see pipeline.py
}
