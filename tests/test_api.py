"""E2E API tests using TestClient."""
import pytest
import tempfile
import os
import json
from unittest import mock
import numpy as np
from fastapi.testclient import TestClient

# Set up test environment
os.environ["OPENAI_API_KEY"] = "test-key-not-real"

EMBED_DIM = 1536


def fake_embedding(text: str) -> list[float]:
    import hashlib
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=EMBED_DIM)
    keyword_axes = {
        "auth": 0, "oauth": 0, "api key": 0, "token": 0,
        "rate limit": 1, "429": 1, "retry": 1,
        "deploy": 2, "kubernetes": 2, "helm": 2, "docker": 2,
        "error": 3, "error_code": 3, "validation": 3,
    }
    lowered = text.lower()
    for kw, axis in keyword_axes.items():
        if kw in lowered:
            vec[axis] += 5.0
    return (vec / np.linalg.norm(vec)).tolist()


class FakeEmbeddingsAPI:
    def create(self, model, input):
        data = [mock.Mock(embedding=fake_embedding(t)) for t in input]
        return mock.Mock(data=data)


class FakeChatAPI:
    def create(self, model, messages, temperature=0):
        system = messages[0]["content"]
        user = messages[1]["content"]
        if "relevance-scoring assistant" in system:
            question = user.split("Question:")[1].split("\n")[0].lower()
            q_words = set(question.split())
            passages = user.split("Candidate passages:")[1].strip().split("\n\n")
            scores = []
            for i, p in enumerate(passages):
                overlap = sum(1 for w in q_words if w in p.lower())
                scores.append({"index": i + 1, "score": min(10, overlap * 3)})
            content = json.dumps(scores)
        elif "fact-checking assistant" in system:
            claims_blocks = user.strip().split("Claim ")[1:]
            results = []
            for block in claims_blocks:
                try:
                    idx = int(block.split(":")[0])
                    results.append({"claim_index": idx, "supported": True})
                except (IndexError, ValueError):
                    pass
            content = json.dumps(results)
        elif "grading whether an answer" in system:
            content = json.dumps({"completeness": 0.9})
        else:
            content = "Based on the documentation, this is answered in the context [1]."
        return mock.Mock(choices=[mock.Mock(message=mock.Mock(content=content))])


class FakeOpenAI:
    def __init__(self, api_key=None):
        self.embeddings = FakeEmbeddingsAPI()
        self.chat = mock.Mock(completions=FakeChatAPI())


@pytest.fixture(scope="session")
def mock_openai():
    """Patch OpenAI for all tests."""
    with mock.patch("pipeline.OpenAI", FakeOpenAI), \
         mock.patch("retrieval.reranker.OpenAI", FakeOpenAI), \
         mock.patch("generation.generate.OpenAI", FakeOpenAI), \
         mock.patch("generation.citations.OpenAI", FakeOpenAI), \
         mock.patch("retrieval.embeddings.OpenAI", FakeOpenAI):
        yield


@pytest.fixture(scope="session")
def temp_qdrant():
    """Create temporary Qdrant directory (session-scoped to avoid locking issues)."""
    tmpdir = tempfile.mkdtemp(prefix="qdrant_test_")
    os.environ["QDRANT_PATH"] = tmpdir
    yield tmpdir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="session")
def shared_pipeline(mock_openai, temp_qdrant):
    """Create a single shared pipeline for all tests."""
    import api
    from config import Settings
    from pipeline import RAGPipeline

    settings = Settings()
    settings.qdrant_path = temp_qdrant
    settings.chunking_strategy = "recursive"

    pipeline = RAGPipeline(settings)
    pipeline.ingest_directory(settings.allowed_ingest_root)

    # Replace lazy pipeline getter
    def mock_get_pipeline():
        return pipeline
    api.get_pipeline = mock_get_pipeline

    yield pipeline


@pytest.fixture
def test_client(shared_pipeline):
    """Create test client with shared pipeline."""
    import api
    client = TestClient(api.app)
    yield client


class TestAuth:
    """Authentication tests."""

    def test_missing_auth(self, test_client):
        response = test_client.post("/v1/ask", json={"question": "test"})
        assert response.status_code == 403

    def test_invalid_auth(self, test_client):
        response = test_client.post(
            "/v1/ask",
            json={"question": "test"},
            headers={"Authorization": "Bearer wrong-key"}
        )
        assert response.status_code == 403

    def test_valid_auth(self, test_client):
        response = test_client.post(
            "/v1/ask",
            json={"question": "What is the rate limit?"},
            headers={"Authorization": "Bearer dev-secret-key"}
        )
        assert response.status_code == 200


class TestAskEndpoint:
    """Tests for /v1/ask endpoint."""

    def test_basic_question(self, test_client):
        response = test_client.post(
            "/v1/ask",
            json={"question": "What authentication methods does Aegis support?"},
            headers={"Authorization": "Bearer dev-secret-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "question" in data
        assert "answer" in data
        assert "sources" in data
        assert "confidence" in data

    def test_answer_structure(self, test_client):
        response = test_client.post(
            "/v1/ask",
            json={"question": "What is the rate limit for API keys?"},
            headers={"Authorization": "Bearer dev-secret-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["confidence"], dict)
        assert "composite" in data["confidence"]
        assert "retrieval_confidence" in data["confidence"]
        assert "citation_coverage" in data["confidence"]
        assert "completeness" in data["confidence"]
        assert isinstance(data["refused"], bool)

    def test_sources_structure(self, test_client):
        response = test_client.post(
            "/v1/ask",
            json={"question": "What is OAuth2 token endpoint?"},
            headers={"Authorization": "Bearer dev-secret-key"}
        )
        assert response.status_code == 200
        data = response.json()
        if data["sources"]:
            source = data["sources"][0]
            assert "block" in source
            assert "source" in source
            assert "fused_score" in source
            assert "rerank_score" in source

    def test_refusal_path(self, test_client, shared_pipeline):
        """Test low-confidence refusal."""
        import api
        from config import Settings
        from pipeline import RAGPipeline

        # Use the shared pipeline but temporarily change the threshold
        original_threshold = shared_pipeline.settings.min_retrieval_confidence
        shared_pipeline.settings.min_retrieval_confidence = 0.99  # Force refusal

        try:
            response = test_client.post(
                "/v1/ask",
                json={"question": "What is the CEO's favorite color?"},
                headers={"Authorization": "Bearer dev-secret-key"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["refused"] is True
            assert data["refusal_reason"] == "retrieval_confidence_below_threshold"
        finally:
            # Restore original threshold
            shared_pipeline.settings.min_retrieval_confidence = original_threshold


class TestIngestEndpoint:
    """Tests for /v1/ingest endpoint."""

    def test_ingest_sample_docs(self, test_client):
        import api
        from config import Settings
        from pipeline import RAGPipeline

        # The shared pipeline already has documents ingested
        # This test verifies the ingest endpoint works when called
        settings = Settings()
        settings.chunking_strategy = "recursive"

        # Create a fresh Qdrant directory for this test
        import tempfile
        import shutil
        tmpdir = tempfile.mkdtemp(prefix="qdrant_ingest_test_")
        try:
            settings.qdrant_path = tmpdir
            pipeline = RAGPipeline(settings)
            api.get_pipeline = lambda: pipeline

            response = test_client.post(
                "/v1/ingest",
                json={"path": settings.allowed_ingest_root},
                headers={"Authorization": "Bearer dev-secret-key"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["documents"] == 3
            assert data["chunks_indexed"] > 0
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_ingest_path_traversal_blocked(self, test_client):
        response = test_client.post(
            "/v1/ingest",
            json={"path": "/etc/passwd"},
            headers={"Authorization": "Bearer dev-secret-key"}
        )
        assert response.status_code == 400
        assert "outside the allowed directory" in response.json()["detail"]


class TestDocumentsEndpoint:
    """Tests for /v1/documents endpoint."""

    def test_list_documents(self, test_client):
        response = test_client.get(
            "/v1/documents",
            headers={"Authorization": "Bearer dev-secret-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total_chunks" in data
        assert isinstance(data["documents"], list)
        assert isinstance(data["total_chunks"], int)
        assert data["total_chunks"] > 0