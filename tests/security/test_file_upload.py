"""Test file upload validation."""
import pytest
import httpx

BASE_URL = "http://localhost:8000"

MALICIOUS_FILES = [
    ("shell.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
    ("shell.jsp", b"<% Runtime.getRuntime().exec(request.getParameter(\"cmd\")); %>", "application/x-jsp"),
    ("test.exe", b"MZ", "application/x-msdownload"),
    ("test.html", b"<script>alert(1)</script>", "text/html"),
    ("test.svg", b"<svg onload=alert(1)>", "image/svg+xml"),
    ("../etc/passwd", b"root:x:0:0:", "text/plain"),
    ("test.phtml", b"<?php echo 'test'; ?>", "application/x-httpd-php"),
    ("test.php5", b"<?php phpinfo(); ?>", "application/x-php"),
]

ALLOWED_FILES = [
    ("doc.pdf", b"%PDF-1.4 test", "application/pdf"),
    ("doc.txt", b"plain text", "text/plain"),
    ("doc.md", b"# markdown", "text/markdown"),
    ("doc.docx", b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("doc.doc", b"\xd0\xcf\x11\xe0", "application/msword"),
]

@pytest.mark.parametrize("filename,content,mime", MALICIOUS_FILES)
def test_malicious_files_rejected(filename, content, mime):
    """Malicious files should be rejected by MIME validation."""
    resp = httpx.post(
        f"{BASE_URL}/v1/demo/upload",
        files={"file": (filename, content, mime)},
        timeout=5.0
    )
    # Should be rejected (400) - not accepted (200)
    assert resp.status_code == 400, f"File {filename} should be rejected, got {resp.status_code}"

@pytest.mark.parametrize("filename,content,mime", ALLOWED_FILES)
def test_allowed_files_accepted(filename, content, mime):
    """Allowed files should pass validation (may fail later due to auth)."""
    resp = httpx.post(
        f"{BASE_URL}/v1/demo/upload",
        files={"file": (filename, content, mime)},
        timeout=5.0
    )
    # Should not be rejected for MIME type (may be 413, 503, 429)
    # 400 means MIME validation failed - that's bad for allowed files
    assert resp.status_code != 400, f"Allowed file {filename} rejected: {resp.status_code}"

def test_extension_mismatch_rejected():
    """Files with mismatched extension/MIME should be rejected."""
    # PDF content with .txt extension
    resp = httpx.post(
        f"{BASE_URL}/v1/demo/upload",
        files={"file": ("doc.txt", b"%PDF-1.4 test", "text/plain")},
        timeout=5.0
    )
    assert resp.status_code == 400

    # HTML content with .pdf extension
    resp = httpx.post(
        f"{BASE_URL}/v1/demo/upload",
        files={"file": ("doc.pdf", b"<html>test</html>", "application/pdf")},
        timeout=5.0
    )
    assert resp.status_code == 400

def test_file_size_limit():
    """Files larger than 10MB should be rejected."""
    # Create 11MB file
    large_content = b"x" * (11 * 1024 * 1024)
    resp = httpx.post(
        f"{BASE_URL}/v1/demo/upload",
        files={"file": ("large.txt", large_content, "text/plain")},
        timeout=10.0
    )
    assert resp.status_code == 413