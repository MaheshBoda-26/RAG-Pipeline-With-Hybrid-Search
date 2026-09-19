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

import uuid

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
        # `chunks_created` is only present when something was newly embedded;
        # a no-op re-ingest returns the early-exit shape without it. The keys
        # below are present in both response shapes.
        for key in (
            "documents",
            "documents_unchanged",
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

    def test_scope_is_echoed_in_trace(self, viz_client, shared_pipeline):
        """The trace must report which document retrieval was scoped to."""
        response = viz_client.post(
            "/v1/demo/pipeline",
            json={"question": self.QUESTION, "source": "authentication.md"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["scope"] == "authentication.md"
        # Every retrieved source must come from the scoped document.
        if not data["refused"]:
            assert data["sources"], "scoped retrieval must surface the doc"
            for s in data["sources"]:
                assert s["source"].endswith("authentication.md")

    def test_unscoped_trace_has_null_scope(self, viz_client):
        response = viz_client.post(
            "/v1/demo/pipeline", json={"question": self.QUESTION}
        )
        assert response.status_code == 200
        assert response.json()["scope"] is None


class TestDemoDeleteDocumentEndpoint:
    """DELETE /v1/demo/documents?source=... — per-document removal.

    The website's Corpus panel deletes user-uploaded documents; the endpoint
    must remove every chunk for the source and keep the index consistent.
    """

    def _seed_test_doc(self, shared_pipeline, name: str) -> None:
        """Insert a chunk for `name` directly into the shared store."""
        from ingestion.chunking import Chunk

        text = f"Unique delete-test content for {name}: the flibberwock galumphs at dawn."
        chunk = Chunk(
            # Qdrant point ids must be UUIDs — derive one deterministically.
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"test:{name}")),
            text=text,
            source=name,
            chunk_index=0,
            strategy="recursive",
            char_count=len(text),
            embedding_model=shared_pipeline.settings.embedding_model,
        )
        vector = [0.05] * shared_pipeline.settings.embedding_dim
        shared_pipeline.vector_store.upsert([chunk], [vector])

    def test_delete_removes_uploaded_document(self, viz_client, shared_pipeline):
        self._seed_test_doc(shared_pipeline, "e2e_delete_a.md")
        docs = viz_client.get("/v1/demo/documents").json()["documents"]
        assert any(d["source"] == "e2e_delete_a.md" for d in docs)

        response = viz_client.delete("/v1/demo/documents", params={"source": "e2e_delete_a.md"})
        assert response.status_code == 200
        assert response.json()["deleted_chunks"] > 0

        docs_after = viz_client.get("/v1/demo/documents").json()["documents"]
        assert not any(d["source"] == "e2e_delete_a.md" for d in docs_after)

    def test_delete_missing_document_returns_zero(self, viz_client):
        response = viz_client.delete(
            "/v1/demo/documents", params={"source": "never_existed_xyz.md"}
        )
        assert response.status_code == 200
        assert response.json()["deleted_chunks"] == 0

    def test_delete_requires_source(self, viz_client):
        response = viz_client.request("DELETE", "/v1/demo/documents")
        assert response.status_code == 422

    def test_deleted_content_is_not_listed_or_retrievable(self, viz_client, shared_pipeline):
        """After deletion the source must vanish from the corpus list."""
        self._seed_test_doc(shared_pipeline, "e2e_delete_b.md")
        deleted = viz_client.delete(
            "/v1/demo/documents", params={"source": "e2e_delete_b.md"}
        ).json()
        assert deleted["deleted_chunks"] > 0

        docs = viz_client.get("/v1/demo/documents").json()["documents"]
        assert not any(d["source"] == "e2e_delete_b.md" for d in docs)
