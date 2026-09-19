"""Cross-encoder reranker using sentence-transformers.

Replaces the LLM-based reranker with a local cross-encoder model for
~10x faster reranking (~120ms vs ~2000ms for 20 candidates on CPU).
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    """Numerically stable logistic sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


class CrossEncoderReranker:
    """Wrapper around sentence-transformers CrossEncoder for reranking."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
        max_length: int = 512,
    ):
        """Initialize the cross-encoder reranker.

        Args:
            model_name: HuggingFace model identifier for the cross-encoder.
            device: Device to run on ("cpu" or "cuda").
            max_length: Maximum sequence length for the model.
        """
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self._model = None

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name, device=self.device, max_length=self.max_length)
                logger.info("Loaded cross-encoder model: %s on %s", self.model_name, self.device)
            except Exception as e:
                logger.error("Failed to load cross-encoder model: %s", e)
                raise

    def rerank(
        self,
        question: str,
        candidates: list[dict],
        top_n: int,
    ) -> list[dict]:
        """Rerank candidates using the cross-encoder.

        Args:
            question: The user's query.
            candidates: List of candidate dicts with 'payload' containing 'text'.
            top_n: Number of top candidates to return.

        Returns:
            Top N candidates sorted by rerank_score (descending), each with
            a 'rerank_score' field added (float 0-10 scale).
        """
        if not candidates:
            return []

        try:
            self._load_model()

            # Prepare pairs: (question, passage_text) for each candidate
            pairs = [(question, c["payload"]["text"]) for c in candidates]

            # Get scores from cross-encoder (raw logits, unbounded range)
            raw_scores = self._model.predict(pairs, show_progress_bar=False)

            # Calibrate to 0-10 via the model-native sigmoid: for ms-marco
            # cross-encoders, sigmoid(logit) is the trained relevance
            # probability, so scores carry ABSOLUTE meaning (a great match is
            # ~9-10, garbage is ~0-1 regardless of what else is in the batch).
            # Never min-max within a batch: that forces the best candidate to
            # 10 even when every candidate is irrelevant, which both corrupts
            # ranking-blind trust in the score and breaks the
            # MIN_RETRIEVAL_CONFIDENCE refusal gate in pipeline.ask().
            rerank_scores = self._normalize_scores(raw_scores)

            # Attach scores to candidates
            for i, c in enumerate(candidates):
                c["rerank_score"] = float(rerank_scores[i])

            # Sort by rerank_score descending and return top_n
            ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
            return ranked[:top_n]

        except Exception as e:
            logger.warning("Cross-encoder reranker failed, falling back to fusion scores: %s", e)
            # Fallback: keep fusion ORDER but cap the reported confidence.
            # RRF fused_score is typically 0.005-0.025; scale by 400 to map to
            # 0-10, then cap at 5.0 (neutral) — fusion rank carries no absolute
            # relevance signal, so reporting >5 would let the pipeline claim
            # confidence it doesn't have and bypass the refusal gate.
            for c in candidates:
                c["rerank_score"] = min(5.0, c.get("fused_score", 0.0) * 400.0)
            ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
            return ranked[:top_n]

    def _normalize_scores(self, raw_scores) -> list[float]:
        """Map raw cross-encoder logits to a calibrated 0-10 relevance scale.

        Uses the model-native sigmoid: score = sigmoid(logit) * 10. Unlike
        batch min-max normalization, this is query-independent and batch-
        independent — a chunk scoring 2.0 is genuinely weak evidence no matter
        what else was retrieved, which is exactly what the downstream
        retrieval-confidence / refusal logic assumes.
        """
        return [round(10.0 * _sigmoid(float(s)), 4) for s in raw_scores]


# Singleton instance for reuse across calls
_reranker_instance: CrossEncoderReranker | None = None


def get_reranker(
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    device: str = "cpu",
    max_length: int = 512,
) -> CrossEncoderReranker:
    """Get or create the singleton cross-encoder reranker instance."""
    global _reranker_instance
    # Check if we need to recreate with different settings
    # Use getattr with defaults to handle mock objects in tests
    if _reranker_instance is None:
        _reranker_instance = CrossEncoderReranker(
            model_name=model_name,
            device=device,
            max_length=max_length,
        )
    elif (getattr(_reranker_instance, 'model_name', None) != model_name or
          getattr(_reranker_instance, 'device', None) != device or
          getattr(_reranker_instance, 'max_length', None) != max_length):
        # Settings changed, recreate
        _reranker_instance = CrossEncoderReranker(
            model_name=model_name,
            device=device,
            max_length=max_length,
        )
    return _reranker_instance


def rerank(
    question: str,
    candidates: list[dict],
    top_n: int,
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    device: str = "cpu",
    max_length: int = 512,
) -> list[dict]:
    """Convenience function matching the old reranker signature.

    Args:
        question: The user's query.
        candidates: List of candidate dicts from fusion.
        top_n: Number of top candidates to return.
        model_name: Cross-encoder model to use.
        device: Device to run on ("cpu" or "cuda").
        max_length: Maximum sequence length.

    Returns:
        Top N candidates sorted by rerank_score, each with rerank_score field.
    """
    reranker = get_reranker(model_name, device, max_length)
    return reranker.rerank(question, candidates, top_n)