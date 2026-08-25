"""Test CORS configuration."""
import pytest
import httpx

BASE_URL = "http://localhost:8000"

def test_cors_allows_localhost():
    """CORS should allow localhost:3000 and 127.0.0.1:3000."""
    for origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
        resp = httpx.options(
            f"{BASE_URL}/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == origin
        assert "authorization" in resp.headers.get("access-control-allow-headers", "").lower()
        assert "content-type" in resp.headers.get("access-control-allow-headers", "").lower()

def test_cors_rejects_evil_origin():
    """CORS should reject unknown origins."""
    resp = httpx.options(
        f"{BASE_URL}/health",
        headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"}
    )
    # Should not allow the evil origin
    assert resp.headers.get("access-control-allow-origin") != "http://evil.com"

def test_cors_no_wildcard():
    """CORS should not use wildcard for credentials."""
    resp = httpx.options(
        f"{BASE_URL}/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    )
    assert resp.headers.get("access-control-allow-origin") != "*"
    assert resp.headers.get("access-control-allow-credentials") == "true"

def test_cors_exposes_retry_after():
    """Retry-After header should be exposed for rate limiting on actual responses."""
    # Test on an actual response that might have Retry-After (rate limited endpoint)
    for i in range(12):
        resp = httpx.post(
            f"{BASE_URL}/v1/demo/ask",
            json={"question": "test"},
            timeout=5.0
        )
        if resp.status_code == 429:
            assert "retry-after" in resp.headers.get("access-control-expose-headers", "").lower()
            return
    # If not rate limited yet, that's ok for this test
    pytest.skip("Rate limit not triggered")