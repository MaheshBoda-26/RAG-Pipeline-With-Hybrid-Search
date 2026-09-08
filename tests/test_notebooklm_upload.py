"""Tests for file upload feature, source-scoped search, and dashboard integration."""
import pytest
from unittest.mock import MagicMock, patch
from api import AskRequest, app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_ask_request_with_source():
    """Verify AskRequest model accepts optional source field."""
    req_no_source = AskRequest(question="What is RAG?")
    assert req_no_source.source is None

    req_with_source = AskRequest(question="Summarize this", source="quarterly_report.pdf")
    assert req_with_source.source == "quarterly_report.pdf"


def test_pipeline_ask_signature_supports_source():
    """Verify pipeline.ask accepts source parameter."""
    from pipeline import RAGPipeline
    import inspect
    sig = inspect.signature(RAGPipeline.ask)
    assert "source" in sig.parameters
    assert sig.parameters["source"].default is None


def test_dashboard_helpers_mocked():
    """Verify dashboard API helper functions format and process requests cleanly."""
    import sys
    from unittest.mock import MagicMock
    if "streamlit" not in sys.modules:
        sys.modules["streamlit"] = MagicMock()

    import streamlit as st
    st.session_state = MagicMock()
    st.session_state.api_url = "http://localhost:8000"
    st.session_state.api_key = "test-key"

    from dashboard.app import upload_file_to_api, delete_document_api, get_documents_api

    with patch("requests.post") as mock_post:
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {
            "message": "File uploaded and indexed",
            "file": "test.txt",
            "chunks_indexed": 3
        }
        res = upload_file_to_api("test.txt", b"Hello world content")
        assert res["file"] == "test.txt"
        assert res["chunks_indexed"] == 3
        assert mock_post.called

    with patch("requests.delete") as mock_del:
        mock_del.return_value.ok = True
        mock_del.return_value.json.return_value = {"message": "Document deleted", "deleted_chunks": 3}
        res = delete_document_api("test.txt")
        assert res["deleted_chunks"] == 3
        assert mock_del.called

    with patch("requests.get") as mock_get:
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"documents": [{"source": "test.txt", "chunk_count": 3}], "total_chunks": 3}
        res = get_documents_api()
        assert len(res["documents"]) == 1
        assert mock_get.called
