"""Tests for the visualization endpoints (Phase 5 differentiators).

Covers:
- /v1/demo/viz     — real chunk coordinates from stored embeddings
- /v1/demo/pipeline — one real ask() run with timings, lanes and confidence

These endpoints power the website's vector-space map and pipeline console.
The invariant under test is honesty: coordinates must derive from stored
vectors, and the trace must match what ask() actually returns.

Reuses the session fixtures from tests/test_api.py (mock_openai, temp_qdrant,
shared_pipeline) so the whole suite runs one mocked pipeline.
"""
from __future__ import annotations

import pytest

from tests.test_api import (  # noqa: F401 — re-exported as fixtures
    mock_openai,
    temp_qdrant,
)
from tests.test_api import shared_pipeline as shared_pipeline_fixture  # noqa: F401

# Re-export under the fixture name pytest resolves.
shared_pipeline = shared_pipeline_fixture


@pytest.fixture(scope="module")
def viz_client(shared_pipeline):
    """TestClient over the shared pipeline used by test_api.py."""
    import api
    from fastapi.testclient import TestClient

    return TestClient(api.app)


class TestVectorSpaceEndpoint:
    """/v1/demo/viz — the corpus as a 3D map."""

    def test_returns_chunks_with_coordinates(self, viz_client, shared_pipeline):
        assert shared_pipeline.vector_store.count() > 0, "corpus must be ingested"
        response = viz_client.get("/v1/demo/viz")
        assert response.status_code == 200
        data = response.json()
        assert data["total_chunks"] > 0
        assert len(data["chunks"]) == data["total_chunks"]
        chunk = data["chunks"][0]
        for key in ("id", "x", "y", "z", "source", "text", "role"):
            assert key in chunk

    def test_coordinates_are_finite_and_bounded(self, viz_client):
        import math

        data = viz_client.get("/v1/demo/viz").json()
        for chunk in data["chunks"]:
            for axis in ("x", "y", "z"):
                assert isinstance(chunk[axis], float)
                assert math.isfinite(chunk[axis])

    def test_projection_is_deterministic(self, viz_client):
        first = viz_client.get("/v1/demo/viz").json()["chunks"]
        second = viz_client.get("/v1/demo/viz").json()["chunks"]
        assert first == second, "same corpus must map to the same coordinates"

    def test_vectors_false_still_returns_points(self, viz_client):
        data = viz_client.get("/v1/demo/viz?vectors=false").json()
        assert data["total_chunks"] > 0
        assert len(data["chunks"]) == data["total_chunks"]

    def test_max_chunks_truncates(self, viz_client, shared_pipeline):
        total = shared_pipeline.vector_store.count()
        if total <= 2:
            pytest.skip("corpus too small to truncate")
        data = viz_client.get("/v1/demo/viz?max_chunks=2").json()
        assert len(data["chunks"]) == 2
        assert data["truncated"] is True

    def test_max_chunks_is_clamped(self, viz_client):
        response = viz_client.get("/v1/demo/viz?max_chunks=nonsense")
        assert response.status_code == 200
        data = viz_client.get("/v1/demo/viz?max_chunks=99999").json()
        assert len(data["chunks"]) <= 2000


class TestPipelineTraceEndpoint:
    """/v1/demo/pipeline — one real ask() with its internals."""

    def test_trace_matches_ask_contract(self, viz_client):
        response = viz_client.post(
            "/v1/demo/pipeline",
            json={"question": "What authentication methods does Aegis support?"},
        )
        assert response.status_code == 200
        data = response.json()

        # The trace is a superset of AskResponse.
        for key in ("question", "answer", "sources", "confidence", "refused"):
            assert key in data
        # ...plus the internals the console renders.
        assert isinstance(data["timings"], dict) and data["timings"]
        assert data["total_ms"] >= 0
        assert isinstance(data["lanes"], dict)

    def test_timings_cover_the_real_stages(self, viz_client):
        data = viz_client.post(
            "/v1/demo/pipeline", json={"question": "What is the rate limit?"}
        ).json()
        # Stages the pipeline always executes, refusals included.
        assert "embed_query" in data["timings"]
        assert "retrieve" in data["timings"]
        assert "rerank" in data["timings"]

    def test_sources_carry_lane_scores(self, viz_client):
        data = viz_client.post(
            "/v1/demo/pipeline",
            json={"question": "What authentication methods does Aegis support?"},
        ).json()
        if data["refused"]:
            pytest.skip("pipeline refused; no scored sources to inspect")
        assert data["sources"], "an answered question must have sources"
        source = data["sources"][0]
        assert "block" in source and "source" in source
        assert "fused_score" in source and "rerank_score" in source

    def test_confidence_breakdown_present(self, viz_client):
        data = viz_client.post(
            "/v1/demo/pipeline", json={"question": "What is the rate limit?"}
        ).json()
        confidence = data["confidence"]
        assert "retrieval_confidence" in confidence
        assert "composite" in confidence

    def test_requires_question(self, viz_client):
        response = viz_client.post("/v1/demo/pipeline", json={})
        assert response.status_code == 422


class TestDemoIngestEndpoint:
    """POST /v1/demo/ingest — seed the demo corpus from the website button."""

    def test_ingest_returns_stats(self, viz_client):
        response = viz_client.post("/v1/demo/ingest")
        assert response.status_code == 200
        data = response.json()
        for key in (
            "documents",
            "documents_unchanged",
            "chunks_created",
            "chunks_indexed",
            "duplicates_skipped",
        ):
            assert key in data
        assert data["documents"] > 0

    def test_ingest_is_idempotent(self, viz_client, shared_pipeline):
        """Clicking the button twice must not duplicate the corpus."""
        before = shared_pipeline.vector_store.count()
        assert before > 0
        viz_client.post("/v1/demo/ingest")
        assert shared_pipeline.vector_store.count() == before


class TestFusionWeightOverrides:
    """Per-query dense/sparse fusion-weight overrides (the demo sliders)."""

    QUESTION = "What authentication methods does Aegis support?"

    def test_trace_without_weights_uses_defaults(self, viz_client):
        response = viz_client.post("/v1/demo/pipeline", json={"question": self.QUESTION})
        assert response.status_code == 200

    def test_trace_accepts_explicit_weights(self, viz_client):
        response = viz_client.post(
            "/v1/demo/pipeline",
            json={"question": self.QUESTION, "dense_weight": 0.9, "sparse_weight": 0.1},
        )
        assert response.status_code == 200
        assert response.json()["answer"]

    def test_out_of_range_weight_is_422(self, viz_client):
        response = viz_client.post(
            "/v1/demo/pipeline", json={"question": "q", "dense_weight": 1.7}
        )
        assert response.status_code == 422

    def test_negative_weight_is_422(self, viz_client):
        response = viz_client.post(
            "/v1/demo/pipeline", json={"question": "q", "sparse_weight": -0.1}
        )
        assert response.status_code == 422

    def test_all_zero_weights_are_422(self, viz_client):
        response = viz_client.post(
            "/v1/demo/pipeline",
            json={"question": "q", "dense_weight": 0.0, "sparse_weight": 0.0},
        )
        assert response.status_code == 422
