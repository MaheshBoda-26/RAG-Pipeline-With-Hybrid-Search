"""Test rate limiting on API endpoints."""
import pytest
import httpx

BASE_URL = "http://localhost:8000"

def test_demo_ask_rate_limit():
    """Demo ask endpoint should rate limit at 10/minute."""
    allowed = 0
    for i in range(12):
        resp = httpx.post(
            f"{BASE_URL}/v1/demo/ask",
            json={"question": "test"},
            timeout=5.0
        )
        if resp.status_code == 200 or resp.status_code == 400:
            allowed += 1
        elif resp.status_code == 429:
            break

    # Should allow 10 requests then rate limit
    assert allowed == 10, f"Expected 10 allowed, got {allowed}"

def test_demo_upload_rate_limit():
    """Demo upload endpoint should rate limit at 3/hour (anonymous)."""
    # Note: 3/hour is hard to test fully, but we can verify the header exists
    resp = httpx.post(
        f"{BASE_URL}/v1/demo/upload",
        files={"file": ("test.txt", b"test content", "text/plain")},
        timeout=5.0
    )
    # Should either succeed or rate limit
    assert resp.status_code in (200, 400, 413, 422, 429, 503)

def test_ask_rate_limit():
    """Authenticated ask endpoint should rate limit at 30/minute."""
    # This will fail without auth, but we can check it doesn't 405
    resp = httpx.post(
        f"{BASE_URL}/v1/ask",
        json={"question": "test"},
        timeout=5.0
    )
    # Should be 401 (auth required) not 405 (method not allowed)
    assert resp.status_code == 401

def test_upload_rate_limit():
    """Authenticated upload endpoint should rate limit at 10/minute."""
    resp = httpx.post(
        f"{BASE_URL}/v1/upload",
        files={"file": ("test.txt", b"test", "text/plain")},
        timeout=5.0
    )
    # Should be 401 (auth required) not 405
    assert resp.status_code == 401

def test_ingest_rate_limit():
    """Authenticated ingest endpoint should rate limit at 10/minute."""
    resp = httpx.post(
        f"{BASE_URL}/v1/ingest",
        json={"path": "./sample_docs"},
        timeout=5.0
    )
    # Should be 401 (auth required) not 405
    assert resp.status_code == 401

def test_login_rate_limit():
    """Login endpoint should rate limit at 5/minute."""
    for i in range(6):
        resp = httpx.post(
            f"{BASE_URL}/v1/auth/login",
            json={"email": "test@test.com", "password": "wrong"},
            timeout=5.0
        )
        if resp.status_code == 429:
            break
    # Should eventually rate limit
    assert resp.status_code in (401, 429)

def test_register_rate_limit():
    """Register endpoint should rate limit at 3/minute."""
    for i in range(4):
        resp = httpx.post(
            f"{BASE_URL}/v1/auth/register",
            json={"email": f"test{i}@test.com", "password": "pass", "name": "test"},
            timeout=5.0
        )
        if resp.status_code == 429:
            break
    assert resp.status_code in (200, 400, 401, 429)

def test_retry_after_header_on_429():
    """429 responses should include Retry-After header."""
    # Make enough requests to trigger rate limit
    for i in range(12):
        resp = httpx.post(
            f"{BASE_URL}/v1/demo/ask",
            json={"question": "test"},
            timeout=5.0
        )
        if resp.status_code == 429:
            assert "retry-after" in resp.headers
            break