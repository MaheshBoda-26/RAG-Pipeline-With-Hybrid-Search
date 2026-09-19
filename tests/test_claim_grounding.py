"""Tests for claim grounding: the signal the refusal gate actually uses."""
from __future__ import annotations

from generation.citations import (
    ClaimCitation,
    LEXICAL_RESCUE_THRESHOLD,
    content_tokens,
    grounded_coverage,
    lexical_support,
)


def passages(*texts: str) -> list[dict]:
    return [{"payload": {"text": text, "source": "doc.md"}} for text in texts]


def test_content_tokens_drop_stopwords_and_keep_identifiers():
    tokens = content_tokens("The retry limit for OAuth2 is 100 requests per minute.")

    assert "oauth2" in tokens
    assert "100" in tokens
    assert "the" not in tokens
    assert "for" not in tokens


def test_lexical_support_measures_content_overlap():
    claim = "The retry limit for OAuth2 is 100 requests per minute."
    source = "OAuth2 clients are limited to 100 requests per minute, then receive 429."

    assert lexical_support(claim, source) > LEXICAL_RESCUE_THRESHOLD


def test_lexical_support_is_zero_for_unrelated_text():
    assert lexical_support("The SLA guarantees 99.99% uptime.", "OAuth2 uses bearer tokens.") == 0.0


def test_grounded_coverage_counts_claims_grounded_anywhere():
    claims = [
        ClaimCitation(1, "supported claim", [1], supported=True, grounded=True),
        ClaimCitation(2, "unsupported claim", [2], supported=False, grounded=False),
    ]

    assert grounded_coverage(claims) == 0.5


def test_grounded_coverage_is_one_without_claims():
    assert grounded_coverage([]) == 1.0


def test_grounded_coverage_ignores_ungrounded_none_verdicts():
    """A claim nobody verified is not grounded."""
    claims = [ClaimCitation(1, "unverified", [1], supported=None, grounded=None)]

    assert grounded_coverage(claims) == 0.0


def test_grounding_distinguishes_miscitation_from_hallucination():
    """The production case: correct fact, wrong citation number."""
    chunks = passages(
        "OAuth2 access tokens are limited to 100 requests per minute.",
        "The Aegis API supports OAuth2 and static API keys.",
    )
    claim = ClaimCitation(
        1,
        "The rate limit for OAuth2 access tokens is 100 requests per minute.",
        cited_blocks=[2],
        supported=False,  # block 2 does not contain the rate limit
    )

    # Lexical rescue finds it in block 1, so the claim is grounded even though
    # the citation number is wrong.
    best_block, best_score = None, 0.0
    for index, chunk in enumerate(chunks, start=1):
        score = lexical_support(claim.sentence, chunk["payload"]["text"])
        if score > best_score:
            best_block, best_score = index, score

    assert best_block == 1
    assert best_score >= LEXICAL_RESCUE_THRESHOLD
