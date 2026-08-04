"""The quality layer most RAG systems skip: after generation, actually check
whether each cited chunk supports the claim it's attached to, and roll that
up into a confidence score the caller can act on (e.g. warn the user, or
refuse to answer).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

CITATION_RE = re.compile(r"\[(\d+)\]")
# Split on sentence boundaries but keep trailing citation brackets attached
# to the sentence they follow, e.g. "...30s [2]." stays one unit.
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")

VERIFY_SYSTEM_PROMPT = """You are a fact-checking assistant. You will be given \
a numbered list of claims, each with the source passage(s) it cites. For each \
claim, decide whether the cited passage(s) actually support it.

Respond with ONLY a JSON array:
[{"claim_index": 1, "supported": true}, {"claim_index": 2, "supported": false}, ...]
No prose, no markdown fences."""

COMPLETENESS_SYSTEM_PROMPT = """You are grading whether an answer fully \
addresses a question, given the source context it was allowed to use. Score \
completeness from 0.0 to 1.0: 1.0 means every part of the question is \
addressed as well as the context allows (including correctly saying "not \
covered" for parts the context doesn't address); lower scores mean parts of \
the question were ignored or glossed over.

Respond with ONLY a JSON object: {"completeness": 0.8}
No prose, no markdown fences."""


@dataclass
class ClaimCitation:
    claim_index: int
    sentence: str
    cited_blocks: list[int]
    supported: bool | None = None  # filled in by verify_citations


def extract_claims(answer_text: str) -> list[ClaimCitation]:
    """Split the answer into sentences and pull out the block numbers each
    one cites. Sentences with no bracketed citation get cited_blocks=[]."""
    raw_sentences = [s.strip() for s in SENTENCE_RE.split(answer_text) if s.strip()]
    claims = []
    for i, sentence in enumerate(raw_sentences):
        cited = [int(n) for n in CITATION_RE.findall(sentence)]
        claims.append(ClaimCitation(claim_index=i + 1, sentence=sentence, cited_blocks=cited))
    return claims


def verify_citations(
    client: OpenAI, model: str, claims: list[ClaimCitation], ranked_chunks: list[dict]
) -> list[ClaimCitation]:
    """Mutates and returns `claims` with `.supported` filled in. Claims with
    no citation are marked unsupported=False by convention -- they're not
    citing anything, so there's nothing to verify (handled separately in
    citation_coverage, which only counts claims that *should* have one)."""
    citing_claims = [c for c in claims if c.cited_blocks]
    if not citing_claims:
        return claims

    blocks_by_num = {i + 1: chunk["payload"]["text"] for i, chunk in enumerate(ranked_chunks)}

    lines = []
    for c in citing_claims:
        cited_text = "\n".join(
            f"  Source [{n}]: {blocks_by_num.get(n, '(citation number not in context -- unsupported)')}"
            for n in c.cited_blocks
        )
        lines.append(f"Claim {c.claim_index}: \"{c.sentence}\"\n{cited_text}")
    user_prompt = "\n\n".join(lines)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        results = json.loads(raw)
        verdict_by_index = {int(r["claim_index"]): bool(r["supported"]) for r in results}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        verdict_by_index = {}

    for c in citing_claims:
        c.supported = verdict_by_index.get(c.claim_index, False)
    return claims


def score_completeness(client: OpenAI, model: str, question: str, answer: str, context: str) -> float:
    user_prompt = f"Question: {question}\n\nContext available:\n{context}\n\nAnswer given:\n{answer}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": COMPLETENESS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return float(json.loads(raw)["completeness"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return 0.5  # neutral fallback rather than crashing the request


def citation_coverage(claims: list[ClaimCitation]) -> float:
    """Fraction of claims that cite something AND are verified as supported,
    out of all claims that cite something at all. A claim with zero
    citations isn't counted against coverage here -- that's a prompt-
    compliance issue (rule 3: say when info is missing), not a citation
    accuracy issue; look at those sentences separately if needed."""
    citing = [c for c in claims if c.cited_blocks]
    if not citing:
        return 1.0  # nothing was cited to be wrong about
    supported = sum(1 for c in citing if c.supported)
    return supported / len(citing)


def retrieval_confidence(ranked_chunks: list[dict]) -> float:
    """Normalized average of the top chunks' rerank scores (0-10 scale from
    the reranker) as a proxy for "did we actually find relevant material."""
    if not ranked_chunks:
        return 0.0
    scores = [c.get("rerank_score", 0.0) for c in ranked_chunks]
    # Use top-3 non-zero scores to avoid penalizing for irrelevant chunks in the pool
    nonzero = [s for s in scores if s > 0]
    if not nonzero:
        return 0.0
    top_scores = sorted(nonzero, reverse=True)[:3]
    return max(0.0, min(1.0, (sum(top_scores) / len(top_scores)) / 10.0))


def composite_confidence(retrieval_conf: float, coverage: float, completeness: float) -> float:
    return round((retrieval_conf + coverage + completeness) / 3.0, 3)
