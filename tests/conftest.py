"""Pytest configuration and fixtures for RAG Pipeline tests."""
import os
from pathlib import Path
from unittest import mock

import pytest
from starlette.testclient import TestClient

# Set test environment variables before importing app
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("NVIDIA_API_KEY", "nvapi-test-key-for-testing-12345")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-testing-only")
os.environ.setdefault("ENABLE_MULTI_TENANT", "false")
os.environ.setdefault("QDRANT_PATH", "./test_qdrant_data")
os.environ.setdefault("COLLECTION_NAME", "test_docs")
os.environ.setdefault("EMBEDDING_DIM", "768")
os.environ.setdefault("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment and cleanup."""
    # Create temp directories
    test_qdrant = Path("./test_qdrant_data")
    test_qdrant.mkdir(exist_ok=True)
    
    test_bm25 = Path("./test_bm25_data")
    test_bm25.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup
    import shutil
    if test_qdrant.exists():
        shutil.rmtree(test_qdrant)
    if test_bm25.exists():
        shutil.rmtree(test_bm25)


@pytest.fixture
def mock_embeddings():
    """Mock embeddings API for deterministic testing."""
    import numpy as np
    import hashlib
    
    EMBED_DIM = 768
    
    def fake_embedding(text: str) -> list[float]:
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
        def create(self, model, input, extra_body=None):
            data = [mock.Mock(embedding=fake_embedding(t)) for t in input]
            return mock.Mock(data=data)
    
    return FakeEmbeddingsAPI()


@pytest.fixture
def mock_chat_api():
    """Mock chat API for deterministic testing."""
    import json
    
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
                claims_blocks = user.strip().split("\n\n")
                results = []
                for block in claims_blocks:
                    idx = int(block.split("Claim ")[1].split(":")[0])
                    results.append({"claim_index": idx, "supported": True})
                content = json.dumps(results)
            
            elif "grading whether an answer" in system:
                content = json.dumps({"completeness": 0.9})
            
            else:
                content = "Based on the documentation, this is answered in the context [1]."
            
            return mock.Mock(choices=[mock.Mock(message=mock.Mock(content=content))])
    
    return FakeChatAPI()


@pytest.fixture
def mock_openai_client(mock_embeddings, mock_chat_api):
    """Create a fully mocked OpenAI client."""
    client = mock.Mock()
    client.embeddings = mock_embeddings
    client.chat.completions = mock_chat_api
    return client


@pytest.fixture
def test_client(mock_openai_client):
    """Create a TestClient with mocked dependencies."""
    # Patch the OpenAI client creation
    with mock.patch("retrieval.embeddings.create_openai_client", return_value=mock_openai_client):
        with mock.patch("pipeline.create_openai_client", return_value=mock_openai_client):
            from api import app
            from config import settings
            
            # Override settings for testing
            settings.qdrant_path = "./test_qdrant_data"
            settings.collection_name = "test_docs"
            settings.embedding_dim = 768
            
            # Create test client
            client = TestClient(app)
            yield client


@pytest.fixture
def authenticated_client(test_client):
    """Create an authenticated test client with JWT cookie."""
    from config import create_access_token
    
    # Create a test user token
    access_token = create_access_token("test_user")
    
    # Set cookie
    test_client.cookies.set("access_token", access_token)
    
    return test_client


@pytest.fixture
def api_key_client(test_client):
    """Create a test client with API key authentication."""
    test_client.headers.update({"Authorization": "Bearer test-api-key"})
    return test_client


@pytest.fixture
def demo_client(test_client):
    """Create a test client for demo endpoints (no auth required)."""
    return test_client


@pytest.fixture
def sample_docs_path():
    """Return path to sample documents."""
    return Path(__file__).parent.parent / "sample_docs"


# Integration test fixtures (require running services)
# These are skipped by default - run with: pytest -m integration

@pytest.fixture(scope="session")
def integration_client():
    """Create a client for integration tests against a real server.
    
    Requires: uvicorn api:app running on localhost:8000
    Set RUN_INTEGRATION_TESTS=1 to enable.
    """
    if not os.environ.get("RUN_INTEGRATION_TESTS"):
        pytest.skip("Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable.")
    
    import httpx
    client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)
    yield client
    client.close()


@pytest.fixture
def integration_auth_client(integration_client):
    """Authenticated integration client."""
    # Login and get token
    resp = integration_client.post("/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpass"
    })
    if resp.status_code == 200:
        # Cookies are automatically handled by httpx
        pass
    return integration_client


def pytest_collection_modifyitems(config, items):
    """Skip tests marked ``integration`` unless RUN_INTEGRATION_TESTS is set.

    Integration tests talk to a live API on localhost:8000. The default unit
    run must stay self-contained (and green) without any running server.
    """
    if os.environ.get("RUN_INTEGRATION_TESTS"):
        return

    skip = pytest.mark.skip(
        reason="integration test: start the API and set RUN_INTEGRATION_TESTS=1"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)