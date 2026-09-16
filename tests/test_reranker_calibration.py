"""Calibration tests for the cross-encoder reranker.

Regression tests for the batch min-max normalization bug: under min-max, the
best-of-batch candidate ALWAYS scored 10.0 even when every candidate was
irrelevant, letting a chunk containing only "plain text" outrank real content
and silently defeating the MIN_RETRIEVAL_CONFIDENCE refusal gate.

After the fix, scores come from the model-native sigmoid and carry absolute
meaning, independent of the rest of the batch.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.cross_encoder_reranker import CrossEncoderReranker, _sigmoid


def _fake_predict_factory(logits: list[float]):
    """Return a mock predict() that yields the given logits in order."""
    def predict(pairs, show_progress_bar=False):
        return list(logits[: len(pairs)])
    return predict


def _candidates(n: int, text: str = "irrelevant filler") -> list[dict]:
    return [{"id": str(i), "payload": {"text": f"{text} {i}"}} for i in range(n)]


def test_irrelevant_batch_never_produces_perfect_score():
    """One relevant + nine irrelevant docs: the irrelevant ones must NOT get 10.

    Under min-max the single relevant doc got 10.0 AND the nearest irrelevant
    doc often scored high too (e.g. 7+), because normalization is relative.
    With sigmoid calibration, irrelevant logits map to genuinely low scores.
    """
    reranker = CrossEncoderReranker()
    # Simulate logits: one strong match (5.0 -> sigmoid~0.993) and nine
    # weak/noise matches (-8.0 .. -4.0 -> sigmoid 0.0003..0.018 -> <=0.18 on 0-10)
    logits = [5.0] + [-8.0, -7.0, -6.0, -6.5, -5.0, -5.5, -4.0, -4.5, -4.2]
    with mock.patch.object(reranker, "_load_model"), \
         mock.patch.object(reranker, "_model") as fake_model:
        fake_model.predict.side_effect = _fake_predict_factory(logits)
        ranked = reranker.rerank("real question", _candidates(10), top_n=10)

    scores = [c["rerank_score"] for c in ranked]
    # The relevant doc is top and high
    assert ranked[0]["rerank_score"] > 9.0
    # Every irrelevant doc is unambiguously low — nothing above 2.0
    assert max(scores[1:]) < 2.0, f"irrelevant scores too high: {scores[1:]}"
    # No score is exactly 10 except a near-perfect sigmoid would be — assert
    # not the min-max artifact where best-of-batch == 10.0 by construction
    assert scores[0] != 10.0 or abs(_sigmoid(5.0) * 10 - 10.0) < 1e-3


def test_all_irrelevant_batch_has_low_top_score():
    """The exact failure from production: ALL candidates irrelevant.

    Previously the top chunk ("plain text") scored 10.0 by min-max
    construction, retrieval_confidence came out 0.748, and the refusal gate
    never fired. Now the top score must reflect true relevance (low).
    """
    reranker = CrossEncoderReranker()
    logits = [-6.0, -7.0, -5.0, -6.5, -5.5]
    with mock.patch.object(reranker, "_load_model"), \
         mock.patch.object(reranker, "_model") as fake_model:
        fake_model.predict.side_effect = _fake_predict_factory(logits)
        ranked = reranker.rerank("what is the weather", _candidates(5), top_n=5)

    top = ranked[0]["rerank_score"]
    # sigmoid(-5) * 10 ~= 0.045; allow a bit of headroom but nothing near 10
    assert top < 1.0, f"all-irrelevant batch produced high top score: {top}"

    # With no dense_score on the candidates, retrieval_confidence (avg of
    # top-3, /10) stays far below any sane MIN_RETRIEVAL_CONFIDENCE -> refusal.
    from generation.citations import retrieval_confidence
    conf = retrieval_confidence(ranked)
    assert conf < 0.35, f"refusal gate defeated: confidence={conf}"


def test_refusal_when_both_signals_weak():
    """Garbage retrieval is low on BOTH signals -> refusal must fire."""
    from generation.citations import retrieval_confidence
    chunks = [
        {"rerank_score": 0.2, "dense_score": 0.31},
        {"rerank_score": 0.1, "dense_score": 0.29},
        {"rerank_score": 0.1, "dense_score": 0.28},
    ]
    assert retrieval_confidence(chunks) < 0.35


def test_strong_dense_rescues_lexically_strict_metaquestion():
    """Meta-questions share no vocabulary with the doc body, so the
    cross-encoder scores ~0 even when dense retrieval found the right chunks
    (cosine ~0.73). The MAX blend means the dense signal rescues these."""
    from generation.citations import retrieval_confidence
    chunks = [
        {"rerank_score": 0.01, "dense_score": 0.7428},
        {"rerank_score": 0.01, "dense_score": 0.7295},
        {"rerank_score": 0.01, "dense_score": 0.7252},
    ]
    conf = retrieval_confidence(chunks)
    assert conf >= 0.35, f"good dense retrieval vetoed by reranker: {conf}"


def test_scores_are_query_independent():
    """Same candidate set must produce identical scores regardless of the other
    candidates in the batch — the core property min-max violated."""
    reranker = CrossEncoderReranker()
    logit = 2.0
    with mock.patch.object(reranker, "_load_model"), \
         mock.patch.object(reranker, "_model") as fake_model:
        fake_model.predict.side_effect = _fake_predict_factory([logit])
        alone = reranker.rerank("q", _candidates(1), top_n=1)[0]["rerank_score"]

        fake_model.predict.side_effect = _fake_predict_factory([logit, -9.0, -9.0])
        in_batch = reranker.rerank("q", _candidates(3), top_n=3)[0]["rerank_score"]

    assert abs(alone - in_batch) < 1e-6, f"{alone} != {in_batch} — scores depend on batch composition"
    assert abs(alone - _sigmoid(logit) * 10) < 1e-3


def test_fallback_caps_confidence_at_neutral():
    """If the cross-encoder crashes, the fused-score fallback must not report
    >5.0 (neutral) — otherwise a broken reranker would bypass the refusal gate."""
    reranker = CrossEncoderReranker()
    cands = _candidates(3)
    for c in cands:
        c["fused_score"] = 0.02  # *400 = 8.0 pre-cap
    with mock.patch.object(reranker, "_load_model", side_effect=RuntimeError("model dead")):
        ranked = reranker.rerank("q", cands, top_n=3)
    assert all(c["rerank_score"] <= 5.0 for c in ranked)


def test_sigmoid_stability():
    """Numerically stable sigmoid: no overflow at extreme logits."""
    assert _sigmoid(1000.0) == 1.0
    assert _sigmoid(-1000.0) == 0.0
    assert abs(_sigmoid(0.0) - 0.5) < 1e-9


if __name__ == "__main__":
    test_irrelevant_batch_never_produces_perfect_score()
    test_all_irrelevant_batch_has_low_top_score()
    test_scores_are_query_independent()
    test_fallback_caps_confidence_at_neutral()
    test_sigmoid_stability()
    print("✅ all reranker calibration tests passed")
