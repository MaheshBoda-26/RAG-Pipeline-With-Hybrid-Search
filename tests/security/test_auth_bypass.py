"""Test that protected endpoints require authentication."""
import pytest
import httpx

BASE_URL = "http://localhost:8000"

PROTECTED_ENDPOINTS = [
    ("POST", "/v1/ask", {"question": "test"}),
    ("POST", "/v1/ingest", {"path": "./sample_docs"}),
    ("POST", "/v1/upload", {"file": ("test.txt", b"test", "text/plain")}),
    ("GET", "/v1/documents", None),
    ("DELETE", "/v1/documents/test.txt", None),
    ("GET", "/v1/auth/me", None),
]

@pytest.mark.parametrize("method,endpoint,body", PROTECTED_ENDPOINTS)
def test_protected_endpoints_require_auth(method, endpoint, body):
    """All protected endpoints should return 401/403 without auth."""
    client = httpx.Client()
    try:
        if method == "GET":
            resp = client.get(f"{BASE_URL}{endpoint}")
        elif method == "POST":
            if body and "file" in body:
                resp = client.post(f"{BASE_URL}{endpoint}", files={"file": body["file"]})
            else:
                resp = client.post(f"{BASE_URL}{endpoint}", json=body)
        elif method == "DELETE":
            resp = client.delete(f"{BASE_URL}{endpoint}")
        else:
            pytest.skip(f"Method {method} not handled")

        # Should be 401 or 403, NOT 405 (method not allowed) or 200
        assert resp.status_code in (401, 403), \
            f"{method} {endpoint}: expected 401/403, got {resp.status_code}"
    finally:
        client.close()

def test_demo_endpoints_public():
    """Demo endpoints should be accessible without auth."""
    resp = httpx.post(f"{BASE_URL}/v1/demo/ask", json={"question": "test"}, timeout=5.0)
    # Should not be 401/403 (may be 200, 400, 429, 503)
    assert resp.status_code not in (401, 403), f"Demo ask should be public: {resp.status_code}"

    resp = httpx.get(f"{BASE_URL}/v1/demo/documents", timeout=5.0)
    assert resp.status_code not in (401, 403), f"Demo documents should be public: {resp.status_code}"

def test_demo_upload_requires_cookie_or_works():
    """Demo upload should work without auth but be rate limited."""
    resp = httpx.post(
        f"{BASE_URL}/v1/demo/upload",
        files={"file": ("test.txt", b"test content", "text/plain")},
        timeout=5.0
    )
    # Should not be 401/403
    assert resp.status_code not in (401, 403)