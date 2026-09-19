"""Query transformation before retrieval — opt-in via ``QUERY_TRANSFORM``.

Short or ambiguous questions are the most common failure mode in retrieval: the
user's phrasing and the corpus's phrasing differ, and dense search returns
topically nearby text that does not answer the question. Two transformations,
both config-gated and both evaluated against the golden set:

- ``rewrite``: one clearer, more specific query. Cheapest, single retrieval.
- ``expand``: the original plus rephrasings. Retrieval runs per query and the
  candidate pools are unioned (see ``pipeline.ask``), which raises recall at the
  cost of one embedding pass per variant.

Every transformation is best-effort: if the model call fails, returns junk, or
returns something that looks like an instruction rather than a query, the
original question is used unchanged. Retrieval must never get *worse* because an
optional enhancement broke.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

MODES = ("none", "rewrite", "expand")

MAX_QUERY_CHARS = 300
MIN_QUERY_CHARS = 3

REWRITE_PROMPT = """Rewrite the user's question so a document search finds the passage that answers it.

Rules:
- Keep every entity, number, identifier and version token exactly as written.
- Add the specific terms a document would use (do not invent facts).
- Output ONE line: the rewritten query. No preamble, no quotes, no numbering."""

EXPAND_PROMPT = """Generate alternative search queries for the user's question.

Rules:
- Each query targets the same answer from a different angle (synonyms, the
  document's likely phrasing, the specific fact being asked for).
- Keep every entity, number, identifier and version token exactly as written.
- Do not answer the question. Do not invent facts.
- Respond with ONLY a JSON array of strings."""

_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_NUMBERING = re.compile(r"^\s*(?:\d+[.)]|[-*])\s*")


def normalize_query(text: str) -> str | None:
    """Return a usable single-line query, or ``None`` when the text is junk."""
    if not text:
        return None
    cleaned = _NUMBERING.sub("", text.strip().splitlines()[0]).strip()
    cleaned = cleaned.strip("\"'` ").strip()
    if not MIN_QUERY_CHARS <= len(cleaned) <= MAX_QUERY_CHARS:
        return None
    # A model that answers instead of rewriting has failed this task.
    if cleaned.lower().startswith(("sure", "here", "as an ai", "the answer", "i cannot")):
        return None
    return cleaned


def _chat(client, model: str, system: str, user: str) -> str | None:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("Query transformation failed, using the original question: %s", exc)
        return None


def dedupe(queries: list[str]) -> list[str]:
    """Case-insensitive de-duplication, preserving order."""
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        key = query.lower()
        if key not in seen:
            seen.add(key)
            unique.append(query)
    return unique


def transform_queries(
    question: str,
    mode: str = "none",
    client=None,
    model: str = "",
    variants: int = 3,
) -> list[str]:
    """Return one or more queries to retrieve with, always starting from ``question``."""
    normalized_mode = (mode or "none").strip().lower()
    if normalized_mode not in MODES:
        logger.warning("Unknown QUERY_TRANSFORM mode %r, using 'none'", mode)
        normalized_mode = "none"

    if normalized_mode == "none" or client is None or not model:
        return [question]

    if normalized_mode == "rewrite":
        raw = _chat(client, model, REWRITE_PROMPT, question)
        rewritten = normalize_query(raw or "")
        if rewritten is None or rewritten.lower() == question.strip().lower():
            return [question]
        return [rewritten]

    # expand: original first (it is the only verified phrasing), then variants.
    raw = _chat(client, model, EXPAND_PROMPT, f"Question: {question}\n\n{variants} queries.")
    candidates: list[str] = []
    match = _JSON_ARRAY.search(raw or "")
    if match:
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            candidates = [q for q in parsed if isinstance(q, str)]

    cleaned = [query for query in (normalize_query(c) for c in candidates) if query]
    queries = dedupe([question, *cleaned])
    return queries[: max(1, variants)]
