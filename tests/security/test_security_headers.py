"""Test security headers on API responses."""
import pytest
import httpx

BASE_URL = "http://localhost:8000"

REQUIRED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}

@pytest.mark.parametrize("endpoint", ["/health", "/v1/demo/ask", "/"])
def test_security_headers_present(endpoint):
    """All endpoints should have security headers."""
    resp = httpx.get(f"{BASE_URL}{endpoint}")
    for header, expected in REQUIRED_HEADERS.items():
        assert header in resp.headers, f"Missing {header} on {endpoint}"
        assert resp.headers[header] == expected, f"Wrong value for {header} on {endpoint}"

def test_csp_header_present():
    """Content-Security-Policy should be present."""
    resp = httpx.get(f"{BASE_URL}/health")
    assert "content-security-policy" in resp.headers
    csp = resp.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src" in csp

def test_hsts_only_on_https():
    """HSTS should NOT be present on HTTP (localhost)."""
    resp = httpx.get(f"{BASE_URL}/health")
    # On localhost HTTP, HSTS should not be set
    assert "strict-transport-security" not in resp.headers

def test_no_server_header_leak():
    """Server header should not leak version info."""
    resp = httpx.get(f"{BASE_URL}/health")
    # Our SecurityHeadersMiddleware removes the server header
    assert "server" not in resp.headers, f"Server header should be removed, got: {resp.headers.get('server')}"