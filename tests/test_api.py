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
        elif "documentation assistant" in system:
            # Generation prompt - check if user content has relevant context
            question = user.split("Question:")[1].split("\n")[0].lower()
            q_words = set(question.split())
            context = user.split("Context:")[1].strip()
            overlap = sum(1 for w in q_words if w in context.lower())
            if overlap > 0:
                content = f"Based on the context, {question.split('?')[0]}. The answer mentions relevant details from the documentation [1]."
            else:
                content = "Based on the documentation, this is answered in the context [1]."
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
    from config import Settings, create_user, load_user_registry, save_user_registry
    from pipeline import RAGPipeline

    # Set up test environment for multi-tenant mode
    settings = Settings()
    settings.qdrant_path = temp_qdrant
    settings.chunking_strategy = "recursive"
    settings.enable_multi_tenant = True
    settings.default_user_id = "default"

    # Create test user with dev-secret-key API key
    registry = load_user_registry()
    registry["default"] = {
        "name": "Test User",
        "api_key": "dev-secret-key",
        "created": __import__("datetime").datetime.now().isoformat()
    }
    save_user_registry(registry)

    pipeline = RAGPipeline(settings)
    pipeline.ingest_directory(settings.allowed_ingest_root)

    # Replace lazy pipeline getter
    def mock_get_pipeline(user_id):
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
            api.get_pipeline = lambda user_id: pipeline

            response = test_client.post(
                "/v1/ingest",
                json={"path": settings.allowed_ingest_root},
                headers={"Authorization": "Bearer dev-secret-key"}
            )
            assert response.status_code == 200
            data = response.json()
            # sample_docs has 3 .md files + 2 user dirs = 5 documents
            assert data["documents"] == 5
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


class TestMultiUserIsolation:
    """Tests for multi-user document isolation."""

    def test_users_see_only_own_documents(self, mock_openai, temp_qdrant):
        """Test that user A cannot see user B's documents."""
        import api
        from config import Settings, create_user, load_user_registry, save_user_registry
        from pipeline import RAGPipeline
        import tempfile
        import shutil

        # Set up multi-tenant mode
        settings = Settings()
        settings.chunking_strategy = "recursive"
        settings.enable_multi_tenant = True
        settings.default_user_id = "default"

        # Create two users with different API keys
        registry = load_user_registry()
        user_a_id = "user_test_a"
        user_b_id = "user_test_b"
        user_a_key = "sk_user_a_test_key_12345"
        user_b_key = "sk_user_b_test_key_67890"
        registry[user_a_id] = {"name": "User A", "api_key": user_a_key, "created": __import__("datetime").datetime.now().isoformat()}
        registry[user_b_id] = {"name": "User B", "api_key": user_b_key, "created": __import__("datetime").datetime.now().isoformat()}
        save_user_registry(registry)

        # Create separate Qdrant directories for each user to avoid locking conflicts
        qdrant_a = tempfile.mkdtemp(prefix="qdrant_user_a_")
        qdrant_b = tempfile.mkdtemp(prefix="qdrant_user_b_")

        try:
            settings_a = Settings()
            settings_a.qdrant_path = qdrant_a
            settings_a.chunking_strategy = "recursive"
            settings_a.enable_multi_tenant = True
            settings_a.default_user_id = "default"

            settings_b = Settings()
            settings_b.qdrant_path = qdrant_b
            settings_b.chunking_strategy = "recursive"
            settings_b.enable_multi_tenant = True
            settings_b.default_user_id = "default"

            # Create pipelines for each user (simulating real get_pipeline behavior)
            pipeline_a = RAGPipeline(settings_a, user_a_id)
            pipeline_b = RAGPipeline(settings_b, user_b_id)

            # Mock get_pipeline to return correct pipeline per user
            def mock_get_pipeline(user_id):
                if user_id == user_a_id:
                    return pipeline_a
                elif user_id == user_b_id:
                    return pipeline_b
                return RAGPipeline(settings, user_id)

            api.get_pipeline = mock_get_pipeline

            # Create test client
            client = TestClient(api.app)

            # Upload different documents for each user
            doc_a_content = "User A's private document about project alpha"
            doc_b_content = "User B's confidential document about project beta"

            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(doc_a_content)
                doc_a_path = f.name
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(doc_b_content)
                doc_b_path = f.name

            # User A uploads their document
            with open(doc_a_path, 'rb') as f:
                response_a = client.post(
                    "/v1/upload",
                    files={"file": ("doc_a.txt", f, "text/plain")},
                    headers={"Authorization": f"Bearer {user_a_key}"}
                )
            assert response_a.status_code == 200
            data_a = response_a.json()
            assert data_a["chunks_indexed"] > 0

            # User B uploads their document
            with open(doc_b_path, 'rb') as f:
                response_b = client.post(
                    "/v1/upload",
                    files={"file": ("doc_b.txt", f, "text/plain")},
                    headers={"Authorization": f"Bearer {user_b_key}"}
                )
            assert response_b.status_code == 200
            data_b = response_b.json()
            assert data_b["chunks_indexed"] > 0

            # User A lists documents - should only see their own
            response_a_list = client.get(
                "/v1/documents",
                headers={"Authorization": f"Bearer {user_a_key}"}
            )
            assert response_a_list.status_code == 200
            docs_a = response_a_list.json()["documents"]
            doc_sources_a = [d["source"] for d in docs_a]
            assert "doc_a.txt" in str(doc_sources_a)
            assert "doc_b.txt" not in str(doc_sources_a)

            # User B lists documents - should only see their own
            response_b_list = client.get(
                "/v1/documents",
                headers={"Authorization": f"Bearer {user_b_key}"}
            )
            assert response_b_list.status_code == 200
            docs_b = response_b_list.json()["documents"]
            doc_sources_b = [d["source"] for d in docs_b]
            assert "doc_b.txt" in str(doc_sources_b)
            assert "doc_a.txt" not in str(doc_sources_b)

            # User A queries - should only find their own content
            response_a_ask = client.post(
                "/v1/ask",
                json={"question": "What is project alpha about?"},
                headers={"Authorization": f"Bearer {user_a_key}"}
            )
            assert response_a_ask.status_code == 200
            answer_a = response_a_ask.json()["answer"]
            assert "alpha" in answer_a.lower() or "project" in answer_a.lower()

            # User B queries - should only find their own content
            response_b_ask = client.post(
                "/v1/ask",
                json={"question": "What is project beta about?"},
                headers={"Authorization": f"Bearer {user_b_key}"}
            )
            assert response_b_ask.status_code == 200
            answer_b = response_b_ask.json()["answer"]
            assert "beta" in answer_b.lower() or "project" in answer_b.lower()

        finally:
            # Cleanup
            os.unlink(doc_a_path)
            os.unlink(doc_b_path)
            shutil.rmtree(qdrant_a, ignore_errors=True)
            shutil.rmtree(qdrant_b, ignore_errors=True)

    def test_separate_qdrant_collections_created(self, mock_openai, temp_qdrant):
        """Test that separate Qdrant collections are created per user."""
        from config import Settings
        from pipeline import RAGPipeline
        from retrieval.vector_store import QdrantVectorStore
        import tempfile
        import shutil

        # Use separate Qdrant directories to avoid locking
        qdrant_a = tempfile.mkdtemp(prefix="qdrant_test_a_")
        qdrant_b = tempfile.mkdtemp(prefix="qdrant_test_b_")

        try:
            settings_a = Settings()
            settings_a.qdrant_path = qdrant_a
            settings_a.enable_multi_tenant = True
            settings_a.user_collection_prefix = "user_"

            settings_b = Settings()
            settings_b.qdrant_path = qdrant_b
            settings_b.enable_multi_tenant = True
            settings_b.user_collection_prefix = "user_"

            # Create pipelines for two users
            pipeline_a = RAGPipeline(settings_a, "user_a")
            pipeline_b = RAGPipeline(settings_b, "user_b")

            # Check collection names are different
            assert pipeline_a.vector_store.collection_name == "user_user_a"
            assert pipeline_b.vector_store.collection_name == "user_user_b"
            assert pipeline_a.vector_store.collection_name != pipeline_b.vector_store.collection_name

            # Check BM25 indexes are separate
            assert pipeline_a.bm25.user_id == "user_a"
            assert pipeline_b.bm25.user_id == "user_b"
        finally:
            shutil.rmtree(qdrant_a, ignore_errors=True)
            shutil.rmtree(qdrant_b, ignore_errors=True)