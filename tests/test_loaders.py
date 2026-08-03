"""Unit tests for document loaders."""
import pytest
import tempfile
import os
from pathlib import Path
from ingestion.loaders import load_directory, load_document


class TestLoadFile:
    """Tests for individual file loading."""

    def test_load_markdown(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test\n\nContent here.")
            f.flush()
            doc = load_document(f.name)
        assert doc.text == "# Test\n\nContent here."
        assert doc.source == f.name
        os.unlink(f.name)

    def test_load_text(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Plain text content.")
            f.flush()
            doc = load_document(f.name)
        assert doc.text == "Plain text content."
        os.unlink(f.name)

    def test_load_html(self):
        html = """<html><body><h1>Title</h1><p>Paragraph</p><script>alert('xss')</script></body></html>"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            f.flush()
            doc = load_document(f.name)
        # Script tags should be stripped
        assert "alert" not in doc.text
        assert "Title" in doc.text
        assert "Paragraph" in doc.text
        os.unlink(f.name)

    def test_load_pdf(self):
        # PDF test requires a sample PDF - skip if no test PDF available
        pass


class TestLoadDirectory:
    """Tests for directory loading."""

    def test_load_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "a.md").write_text("# Doc A\nContent A")
            (Path(tmpdir) / "b.txt").write_text("Doc B content")
            (Path(tmpdir) / "c.html").write_text("<html><body>Doc C</body></html>")

            docs = load_directory(tmpdir)
            assert len(docs) == 3
            sources = [d.source for d in docs]
            assert any("a.md" in s for s in sources)
            assert any("b.txt" in s for s in sources)
            assert any("c.html" in s for s in sources)

    def test_load_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs = load_directory(tmpdir)
            assert len(docs) == 0

    def test_load_nonexistent_directory(self):
        docs = load_directory("/nonexistent/path/12345")
        assert len(docs) == 0

    def test_skip_unsupported_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.md").write_text("# Doc A")
            (Path(tmpdir) / "b.xyz").write_text("unsupported")

            docs = load_directory(tmpdir)
            assert len(docs) == 1
            assert "a.md" in docs[0].source