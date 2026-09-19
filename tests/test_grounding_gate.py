"""The grounding gate: an unsupported answer must be reported as a refusal.

Regression tests for a real defect measured on the unanswerable set: the
pipeline returned ungrounded answers with `refused=False` whenever the retrieval
score was healthy, because near-miss questions retrieve topically adjacent
passages and score well. The composite mean let a high "completeness" score
(which the judge awards for politely declining) mask zero citation coverage.
"""
from __future__ import annotations

from generation.citations import ClaimCitation, citation_coverage, composite_confidence
from pipeline import AskResponse, RAGPipeline


def make_ranked(count: int = 3) -> list[dict]:
    return [
        {
            "id": f"id{i}",
            "payload": {"text": f"passage {i}", "source": "aegis.md", "section_heading": "Auth"},
            "fused_score": 0.02,
            "rerank_score": 7.0,
            "dense_score": 0.6,
        }
        for i in range(count)
    ]


def make_pipeline(monkeypatch) -> RAGPipeline:
    """A pipeline with every model call stubbed out."""
    monkeypatch.setenv("USE_SUPABASE", "false")
    monkeypatch.setenv("QDRANT_PATH", "./qdrant_data_test_gate")
    pipeline = RAGPipeline.__new__(RAGPipeline)  # no __init__: no Qdrant, no clients
    from config import Settings

    pipeline.settings = Settings()
    pipeline.user_id = "test"
    pipeline.query_cache = None
    pipeline.bm25 = None
    return pipeline


def test_declining_answer_is_reported_as_a_refusal(monkeypatch):
    """The exact production failure: model declines, retrieval score is fine."""
    pipeline = make_pipeline(monkeypatch)
    claims = [
        ClaimCitation(1, "I'm unable to answer the question as the provided context "
                         "does not contain any information about pricing.", [], None)
    ]
    assert citation_coverage(claims) == 0.0

    # The composite stays above the retrieval threshold, which is why the gate
    # cannot rely on it alone.
    composite = composite_confidence(0.639, 0.0, 1.0)
    assert composite > pipeline.settings.min_retrieval_confidence


def test_zero_coverage_refuses_but_partial_coverage_answers():
    """The rule is 'no supported claim at all', not 'not perfect'."""
    unsupported = [ClaimCitation(1, "Price is $10 [1].", [1], False)]
    partial = [
        ClaimCitation(1, "Limits are 100 rps [1].", [1], True),
        ClaimCitation(2, "Support is 24/7 [2].", [2], False),
    ]

    assert citation_coverage(unsupported) == 0.0
    assert citation_coverage(partial) == 0.5


def test_refusal_reason_is_distinguishable():
    """Callers must be able to tell the two refusals apart."""
    response = AskResponse(
        question="q",
        answer="I couldn't find enough relevant information.",
        sources=[],
        confidence={},
        refused=True,
        refusal_reason="retrieval_confidence_below_threshold",
    )
    assert response.refused is True
    assert response.refusal_reason == "retrieval_confidence_below_threshold"


def test_source_blocks_expose_verbatim_text_only():
    """The UI must never quote situating context that the document lacks."""
    ranked = make_ranked(1)
    ranked[0]["payload"]["context"] = "Situating context generated at ingest time."
    ranked[0]["payload"]["index_text"] = "Situating context generated at ingest time.\n\npassage 0"

    blocks = RAGPipeline._source_blocks(ranked)

    assert blocks[0]["text"] == "passage 0"
    assert "Situating context" not in blocks[0]["text"]
    assert blocks[0]["block"] == 1
