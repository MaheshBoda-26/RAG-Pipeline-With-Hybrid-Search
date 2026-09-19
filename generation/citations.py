"""The quality layer most RAG systems skip: after generation, actually check
whether each cited chunk supports the claim it's attached to, and roll that
up into a confidence score the caller can act on (e.g. warn the user, or
refuse to answer).
"""
from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
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

COMPLETENESS_SYSTEM_PROMPT = """You are grading an answer to a question, given the source \
context it was allowed to use. Report two independent judgments.

1. completeness: 0.0-1.0, whether the answer addresses every part of the \
question as well as the context allows. Correctly saying "not covered" for a \
part the context does not address still counts as addressing it; ignoring or \
glossing over a part does not.

2. answerable: whether the CONTEXT contains the information needed to answer \
the QUESTION (or the material parts of it). This is a statement about the \
context, not about the answer: if the context lacks the information, \
answerable is false no matter how clearly the answer says so. Judge only the \
context — what you may know from elsewhere is irrelevant.

Respond with ONLY a JSON object: {"completeness": 0.8, "answerable": true}
No prose, no markdown fences."""


# A claim the judge called unsupported is rescued when it is almost verbatim
# present in a retrieved passage: the judge is a small model and produces false
# negatives, and a false negative here refuses a correct answer. The threshold
# is deliberately high so the rescue cannot rescue a fabrication.
LEXICAL_RESCUE_THRESHOLD = 0.6

_CONTENT_STOPWORDS = frozenset(
    """a an and are as at be been by can could do does for from had has have he her his
    how i if in into is it its may might must no not of on or our should so than that the
    their them then there these they this to was we were what when where which who why will
    with would you your""".split()
)
# Tokens are alphanumeric runs, optionally joined by . or - (so "bge-base",
# "0.95" and "aegis_live" stay single tokens) but never ending in punctuation —
# "minute." and "minute" must be the same token.
_TOKEN_RE = re.compile(r"[a-z0-9_]+(?:[.\-][a-z0-9_]+)*")


def content_tokens(text: str) -> set[str]:
    """Lowercased content words: what a claim and a passage must share to be
    talking about the same fact."""
    return {
        token for token in _TOKEN_RE.findall((text or "").lower())
        if token not in _CONTENT_STOPWORDS and len(token) > 1
    }


def lexical_support(claim: str, passage: str) -> float:
    """Fraction of the claim's content words present in the passage."""
    want = content_tokens(claim)
    if not want:
        return 0.0
    return len(want & content_tokens(passage)) / len(want)


@dataclass
class ClaimCitation:
    claim_index: int
    sentence: str
    cited_blocks: list[int]
    supported: bool | None = None  # filled in by verify_citations
    # ``grounded`` is the wider question the refusal gate needs: does any
    # retrieved passage support this claim? A model that cites [2] for a fact
    # that lives in [1] has a citation defect (tracked by ``supported``) but is
    # not hallucinating, and refusing a correct answer over a numbering slip is
    # the wrong trade.
    grounded: bool | None = None
    grounded_block: int | None = None


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

    passages = [(i + 1, chunk["payload"]["text"]) for i, chunk in enumerate(ranked_chunks)]
    for c in citing_claims:
        c.supported = verdict_by_index.get(c.claim_index, False)
        if c.supported:
            c.grounded = True
            c.grounded_block = c.cited_blocks[0]
            continue
        # Rescue rule: the judge says unsupported, but is the claim's content
        # actually present in a retrieved passage? Highest overlap wins.
        best_block, best_score = None, 0.0
        for block, text in passages:
            score = lexical_support(c.sentence, text)
            if score > best_score:
                best_block, best_score = block, score
        c.grounded = best_score >= LEXICAL_RESCUE_THRESHOLD
        c.grounded_block = best_block if c.grounded else None
    return claims


def parse_completeness(raw: str) -> tuple[float, bool | None]:
    """Parse the completeness/answerability judge, tolerating partial output.

    Returns ``(completeness, answerable)``; ``answerable`` is ``None`` when the
    judge did not say, which callers must treat as "unknown", not as "no".
    """
    cleaned = (raw or "").removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0.5, None  # neutral fallback rather than crashing the request
    try:
        completeness = float(data["completeness"])
    except (KeyError, TypeError, ValueError):
        completeness = 0.5
    answerable = data.get("answerable")
    return completeness, answerable if isinstance(answerable, bool) else None


def score_completeness(client: OpenAI, model: str, question: str, answer: str, context: str) -> float:
    """Completeness only. Prefer ``score_completeness_and_answerability``."""
    return score_completeness_and_answerability(client, model, question, answer, context)[0]


def score_completeness_and_answerability(
    client: OpenAI, model: str, question: str, answer: str, context: str
) -> tuple[float, bool | None]:
    """Grade the answer and, in the same call, whether the context could answer.

    Answerability is what detects a near-miss question: an answer that politely
    declines still scores high completeness, so completeness alone cannot tell a
    grounded answer from an honest "I couldn't find it".
    """
    user_prompt = f"Question: {question}\n\nContext available:\n{context}\n\nAnswer given:\n{answer}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": COMPLETENESS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    return parse_completeness(resp.choices[0].message.content)


def citation_coverage(claims: list[ClaimCitation]) -> float:
    """Fraction of ALL claims that are verified as supported,
    out of all claims in the answer.

    Previously, only claims with citations were counted in the denominator,
    which allowed uncited hallucinations to receive 100% confidence even
    when they contained unsupported factual claims. Now uncited claims are
    treated as unsupported (no evidence was provided), properly penalizing
    answers that contain claims without citation.

    A claim with zero citations is counted as unsupported in the denominator,
    since they have no source evidence to verify against."""
    if not claims:
        return 1.0  # no claims to evaluate
    total = len(claims)
    supported = sum(1 for c in claims if c.cited_blocks and c.supported)
    # Uncited claims (cited_blocks is empty) are treated as unsupported
    # since they have no source evidence to verify against.
    return supported / total


def grounded_coverage(claims: list[ClaimCitation]) -> float:
    """Fraction of claims supported by *some* retrieved passage.

    This is the refusal gate's signal: it distinguishes "the model invented
    this" from "the model cited the wrong passage number", which is the
    difference between an ungrounded answer and a formatting slip.
    """
    if not claims:
        return 1.0
    grounded = sum(1 for c in claims if c.grounded)
    return grounded / len(claims)


def retrieval_confidence(ranked_chunks: list[dict]) -> float:
    """Blend of cross-encoder relevance and dense-similarity signal.

    Two independent views of "did we retrieve relevant material":

    - rerank_score (calibrated 0-10 from the ms-marco cross-encoder):
      excellent at detecting TRUE relevance, but lexically strict — a
      meta-question like "who is in this document?" shares no vocabulary
      with the document body and can score ~0 even when dense retrieval
      nailed the right chunks.
    - dense cosine similarity from the vector store (carried through as
      'dense_score' on candidates by the retrieval layer): robust to
      vocabulary mismatch, weaker at fine-grained relevance.

    Taking the MAX of the two signals per chunk means neither view can
    alone veto a good retrieval; both must agree the retrieval is BAD to
    trigger refusal. This preserves the calibrated refusal gate (garbage
    queries score ~0 on both signals) while not punishing queries whose
    phrasing the cross-encoder dislikes.
    """
    if not ranked_chunks:
        return 0.0

    def _chunk_conf(c: dict) -> float:
        rerank = (c.get("rerank_score") or 0.0) / 10.0
        dense = c.get("dense_score")
        dense = float(dense) if dense is not None else 0.0
        return max(rerank, dense)

    per_chunk = [_chunk_conf(c) for c in ranked_chunks]
    top_scores = sorted(per_chunk, reverse=True)[:3]
    return max(0.0, min(1.0, sum(top_scores) / len(top_scores)))


def composite_confidence(retrieval_conf: float, coverage: float, completeness: float) -> float:
    return round((retrieval_conf + coverage + completeness) / 3.0, 3)


async def verify_citations_and_completeness_parallel(
    client: OpenAI,
    model: str,
    claims: list[ClaimCitation],
    ranked_chunks: list[dict],
    question: str,
    answer: str,
    context: str,
) -> tuple[list[ClaimCitation], float, bool | None]:
    """Run verify_citations and score_completeness in parallel using asyncio.

    This reduces latency by ~50% compared to sequential execution since both
    LLM calls can run simultaneously.

    Args:
        client: OpenAI client
        model: Chat model name
        claims: List of claims to verify
        ranked_chunks: Ranked chunks for citation verification
        question: Original question
        answer: Generated answer
        context: Context string for completeness scoring

    Returns:
        Tuple of (verified_claims, completeness_score, answerable)
    """
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=2)

    def run_verify():
        return verify_citations(client, model, claims, ranked_chunks)

    def run_grade():
        return score_completeness_and_answerability(client, model, question, answer, context)

    # Run both in parallel
    verify_task = loop.run_in_executor(executor, run_verify)
    grade_task = loop.run_in_executor(executor, run_grade)

    verified_claims, (completeness, answerable) = await asyncio.gather(verify_task, grade_task)
    executor.shutdown(wait=False)

    return verified_claims, completeness, answerable


def verify_citations_and_completeness_sync(
    client: OpenAI,
    model: str,
    claims: list[ClaimCitation],
    ranked_chunks: list[dict],
    question: str,
    answer: str,
    context: str,
) -> tuple[list[ClaimCitation], float, bool | None]:
    """Synchronous wrapper for parallel verification and grading.

    Uses ThreadPoolExecutor to run both LLM calls concurrently. Returns
    ``(claims, completeness, answerable)``.
    """
    with ThreadPoolExecutor(max_workers=2) as executor:
        verify_future = executor.submit(verify_citations, client, model, claims, ranked_chunks)
        grade_future = executor.submit(
            score_completeness_and_answerability, client, model, question, answer, context
        )

        verified_claims = verify_future.result()
        completeness, answerable = grade_future.result()

    return verified_claims, completeness, answerable
