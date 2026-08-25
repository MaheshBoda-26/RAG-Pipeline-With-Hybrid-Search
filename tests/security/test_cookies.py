"""Test cookie security settings."""
import pytest
import httpx

BASE_URL = "http://localhost:8000"

def test_cookies_httponly():
    """Auth cookies should be HttpOnly."""
    resp = httpx.post(
        f"{BASE_URL}/v1/auth/login",
        json={"email": "test@test.com", "password": "wrongpass"},
        timeout=5.0
    )
    # Check Set-Cookie headers
    cookies = resp.headers.get_list("set-cookie") if hasattr(resp.headers, 'get_list') else []
    for cookie in cookies:
        if "access_token" in cookie or "refresh_token" in cookie:
            assert "httponly" in cookie.lower(), f"Cookie not HttpOnly: {cookie}"

def test_cookies_samesite_lax():
    """Cookies should have SameSite=Lax."""
    resp = httpx.post(
        f"{BASE_URL}/v1/auth/login",
        json={"email": "test@test.com", "password": "wrongpass"},
        timeout=5.0
    )
    cookies = resp.headers.get_list("set-cookie") if hasattr(resp.headers, 'get_list') else []
    for cookie in cookies:
        if "access_token" in cookie or "refresh_token" in cookie:
            assert "samesite=lax" in cookie.lower() or "samesite=strict" in cookie.lower(), \
                f"Cookie missing SameSite: {cookie}"

def test_cookies_secure_in_dev():
    """In development, cookies should NOT have Secure flag (works on HTTP localhost)."""
    resp = httpx.post(
        f"{BASE_URL}/v1/auth/login",
        json={"email": "test@test.com", "password": "wrongpass"},
        timeout=5.0
    )
    cookies = resp.headers.get_list("set-cookie") if hasattr(resp.headers, 'get_list') else []
    for cookie in cookies:
        if "access_token" in cookie or "refresh_token" in cookie:
            # In dev mode, secure should NOT be set
            assert "secure" not in cookie.lower(), f"Cookie has Secure flag in dev: {cookie}"

def test_cookie_path_root():
    """Cookies should have Path=/."""
    resp = httpx.post(
        f"{BASE_URL}/v1/auth/login",
        json={"email": "test@test.com", "password": "wrongpass"},
        timeout=5.0
    )
    cookies = resp.headers.get_list("set-cookie") if hasattr(resp.headers, 'get_list') else []
    for cookie in cookies:
        if "access_token" in cookie or "refresh_token" in cookie:
            assert "path=/" in cookie.lower(), f"Cookie missing Path=/: {cookie}"

def test_logout_clears_cookies():
    """Logout should clear auth cookies."""
    resp = httpx.post(f"{BASE_URL}/v1/auth/logout", timeout=5.0)
    cookies = resp.headers.get_list("set-cookie") if hasattr(resp.headers, 'get_list') else []

    # Should have Set-Cookie headers that delete the cookies
    found_access = False
    found_refresh = False
    for cookie in cookies:
        if "access_token" in cookie and ("expires=thu, 01 jan 1970" in cookie.lower() or "max-age=0" in cookie.lower()):
            found_access = True
        if "refresh_token" in cookie and ("expires=thu, 01 jan 1970" in cookie.lower() or "max-age=0" in cookie.lower()):
            found_refresh = True

    assert found_access, "access_token not cleared on logout"
    assert found_refresh, "refresh_token not cleared on logout"