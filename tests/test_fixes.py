"""Regression tests for the recent bug fixes.

Covers:
- config.py: email lookup, cookie_secure
- api.py: token extraction, upload validation no NameError
- pipeline.py: refusal message source listing
- retrieval/supabase_store.py: stable upsert IDs
- retrieval/vector_store.py: dim mismatch warning
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from io import BytesIO
from unittest import mock

import numpy as np
import pytest
from fastapi.testclient import TestClient


os.environ["OPENAI_API_KEY"] = "test-key-not-real"

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
            content = __import__("json").dumps(scores)
        elif "fact-checking assistant" in system:
            claims_blocks = user.strip().split("Claim ")[1:]
            results = []
            for block in claims_blocks:
                try:
                    idx = int(block.split(":")[0])
                    results.append({"claim_index": idx, "supported": True})
                except (IndexError, ValueError):
                    pass
            content = __import__("json").dumps(results)
        elif "grading whether an answer" in system:
            content = __import__("json").dumps({"completeness": 0.9})
        else:
            content = "Based on the documentation, this is answered in the context [1]."
        return mock.Mock(choices=[mock.Mock(message=mock.Mock(content=content))])


class FakeOpenAI:
    def __init__(self, api_key=None, base_url=None, **kwargs):
        self.embeddings = FakeEmbeddingsAPI()
        self.chat = mock.Mock(completions=FakeChatAPI())


@pytest.fixture(scope="module")
def mock_openai_module():
    with mock.patch("pipeline.OpenAI", FakeOpenAI), \
         mock.patch("retrieval.reranker.OpenAI", FakeOpenAI), \
         mock.patch("generation.generate.OpenAI", FakeOpenAI), \
         mock.patch("generation.citations.OpenAI", FakeOpenAI), \
         mock.patch("retrieval.embeddings.OpenAI", FakeOpenAI):
        yield


@pytest.fixture(scope="module")
def temp_qdrant_dir():
    tmpdir = tempfile.mkdtemp(prefix="qdrant_fix_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="module")
def registry_backup():
    from config import USER_REGISTRY_PATH

    original = USER_REGISTRY_PATH.read_text() if USER_REGISTRY_PATH.exists() else None
    yield
    if original is None:
        if USER_REGISTRY_PATH.exists():
            USER_REGISTRY_PATH.unlink()
    else:
        USER_REGISTRY_PATH.write_text(original)


@pytest.fixture(scope="module")
def base_settings(mock_openai_module, temp_qdrant_dir, registry_backup):
    from config import Settings, load_user_registry, save_user_registry

    registry = load_user_registry()
    registry["default"] = {
        "name": "Test User",
        "email": "dev@example.com",
        "api_key": "dev-secret-key",
        "created": "2025-01-01T00:00:00",
        "role": "user",
    }
    save_user_registry(registry)

    settings = Settings()
    settings.qdrant_path = temp_qdrant_dir
    settings.use_supabase = False
    settings.chunking_strategy = "recursive"
    settings.enable_multi_tenant = True
    settings.default_user_id = "default"
    return settings


@pytest.fixture(scope="module")
def pipeline(base_settings):
    from pipeline import RAGPipeline
    import retrieval.vector_store as vector_store_module

    vector_store_module._embedded_client = None
    p = RAGPipeline(base_settings)
    p.ingest_directory(base_settings.allowed_ingest_root)
    return p


@pytest.fixture(scope="module")
def api_client(base_settings, pipeline):
    import api

    api.get_pipeline = lambda user_id: pipeline
    return TestClient(api.app)


class TestConfigFixes:
    def test_get_user_by_email_ignores_name(self):
        from config import get_user_by_email, load_user_registry, save_user_registry

        registry = load_user_registry()
        uid = "user_regression_name_only"
        registry[uid] = {
            "name": "NotAnEmail",
            "email": "real@example.com",
            "api_key": "sk_test_123",
            "created": "2025-01-01T00:00:00",
        }
        save_user_registry(registry)
        try:
            assert get_user_by_email("real@example.com") == uid
            assert get_user_by_email("NotAnEmail") is None
        finally:
            registry.pop(uid, None)
            save_user_registry(registry)

    def test_cookie_secure_reads_current_env(self):
        from config import Settings

        with mock.patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            assert Settings().cookie_secure is True
        with mock.patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            assert Settings().cookie_secure is False


class TestApiHelpersAndUploads:
    def test_get_token_from_request(self):
        from api import _get_token_from_request

        req = mock.Mock()
        req.cookies = {"access_token": "cookie-token"}
        req.headers = {"Authorization": "Bearer header-token"}
        # When cookie value is passed as second arg, it takes precedence
        assert _get_token_from_request(req, "cookie-token") == "cookie-token"
        # When no cookie value passed, falls back to Authorization header
        assert _get_token_from_request(req) == "header-token"

    def test_get_token_from_request_uses_bearer_header(self):
        from api import _get_token_from_request

        req = mock.Mock()
        req.cookies = {}
        req.headers = {"Authorization": "Bearer header-token"}
        assert _get_token_from_request(req) == "header-token"

    def test_upload_invalid_extension_returns_400(self, api_client):
        response = api_client.post(
            "/v1/upload",
            files={"file": ("malware.exe", BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
            headers={"Authorization": "Bearer dev-secret-key"},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_demo_upload_invalid_extension_returns_400(self, api_client):
        response = api_client.post(
            "/v1/demo/upload",
            files={"file": ("malware.exe", BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]


class TestPipelineRefusalMessage:
    def test_refusal_includes_sources_when_candidates_exist(self, pipeline):
        original = pipeline.settings.min_retrieval_confidence
        pipeline.settings.min_retrieval_confidence = 0.999
        try:
            response = pipeline.ask("What is the RAG pipeline?")
            assert response.refused is True
            assert "check the following documents manually" in response.answer
        finally:
            pipeline.settings.min_retrieval_confidence = original

    def test_refusal_generic_when_no_candidates(self, pipeline):
        original_threshold = pipeline.settings.min_retrieval_confidence
        original_embed = pipeline.embedder.embed_one
        original_query = pipeline.vector_store.query
        original_sparse = pipeline.bm25.query

        pipeline.settings.min_retrieval_confidence = 0.999
        pipeline.embedder.embed_one = lambda _: [0.0] * EMBED_DIM
        pipeline.vector_store.query = lambda *_args, **_kwargs: []
        pipeline.bm25.query = lambda *_args, **_kwargs: []

        try:
            response = pipeline.ask("gibberish that matches nothing")
            assert response.refused is True
            assert "any relevant information" in response.answer
        finally:
            pipeline.settings.min_retrieval_confidence = original_threshold
            pipeline.embedder.embed_one = original_embed
            pipeline.vector_store.query = original_query
            pipeline.bm25.query = original_sparse


class TestSupabaseStoreFixes:
    def test_upsert_uses_chunk_ids(self):
        from ingestion.chunking import Chunk
        from retrieval.supabase_store import SupabaseVectorStore

        mock_client = mock.Mock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = mock.Mock()

        store = SupabaseVectorStore.__new__(SupabaseVectorStore)
        store.collection_name = "test"
        store.collection_id = "existing-col-id"
        store.client = mock_client

        chunks = [
            Chunk(id="chunk-aaa", text="hello", source="a.txt", chunk_index=0, strategy="fixed", char_count=5),
            Chunk(id="chunk-bbb", text="world", source="b.txt", chunk_index=1, strategy="fixed", char_count=5),
        ]
        embeddings = [[0.1] * EMBED_DIM, [0.2] * EMBED_DIM]

        store.upsert(chunks, embeddings)
        inserted = mock_client.table.return_value.upsert.call_args[0][0]
        assert [row["id"] for row in inserted] == ["chunk-aaa", "chunk-bbb"]


class TestQdrantDimMismatchWarning:
    def test_dim_mismatch_logs_warning(self, caplog):
        import qdrant_client.models as qmodels
        from qdrant_client import QdrantClient
        import retrieval.vector_store as vector_store_module
        import tempfile
        import shutil

        tmpdir = tempfile.mkdtemp(prefix="qdrant_dim_test_standalone_")
        vector_store_module._embedded_client = None

        try:
            client = QdrantClient(path=tmpdir, force_disable_check_same_thread=True)
            client.create_collection(
                collection_name="dim_test_coll",
                vectors_config={
                    "default": qmodels.VectorParams(size=512, distance=qmodels.Distance.COSINE)
                },
            )
            client.close()

            with caplog.at_level(logging.WARNING, logger="retrieval.vector_store"):
                from retrieval.vector_store import QdrantVectorStore
                store = QdrantVectorStore(
                    path=tmpdir,
                    url="",
                    collection_name="dim_test_coll",
                    embedding_dim=768,
                )

            assert "dimension mismatch" in caplog.text.lower()
            info = store.client.get_collection("dim_test_coll")
            vectors_cfg = info.config.params.vectors
            if isinstance(vectors_cfg, dict):
                size = vectors_cfg["default"].size
            else:
                size = vectors_cfg.size
            assert size == 768
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
