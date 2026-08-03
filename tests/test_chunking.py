"""Unit tests for chunking strategies."""
import pytest
from pathlib import Path
from ingestion.chunking import (
    Chunk,
    chunk_fixed,
    chunk_recursive,
    chunk_semantic,
)
from ingestion.loaders import RawDocument


class TestChunkFixed:
    """Tests for fixed-size chunking."""

    def test_basic_chunking(self):
        text = "a" * 1000
        doc = RawDocument(source="test.txt", text=text, doc_type="txt")
        chunks = chunk_fixed(doc, size=500, overlap=50)
        # With size=500, overlap=50, step=450: 0-500, 450-950, 900-1000
        assert len(chunks) == 3
        assert chunks[0].char_count == 500
        assert chunks[1].char_count == 500
        assert chunks[2].char_count == 100

    def test_short_text_single_chunk(self):
        text = "short text"
        doc = RawDocument(source="test.txt", text=text, doc_type="txt")
        chunks = chunk_fixed(doc, size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_empty_text(self):
        text = ""
        doc = RawDocument(source="test.txt", text=text, doc_type="txt")
        chunks = chunk_fixed(doc, size=500, overlap=50)
        assert len(chunks) == 0

    def test_overlap_larger_than_chunk(self):
        text = "a" * 100
        doc = RawDocument(source="test.txt", text=text, doc_type="txt")
        # When overlap >= size, step becomes 1 (max(size - overlap, 1))
        chunks = chunk_fixed(doc, size=50, overlap=100)
        # This creates many small chunks - just verify it doesn't crash
        assert len(chunks) > 0


class TestChunkRecursive:
    """Tests for recursive (structure-aware) chunking."""

    def test_markdown_headings_split(self):
        text = """# Heading 1
Content 1
## Subheading 1.1
Content 1.1
# Heading 2
Content 2"""
        doc = RawDocument(source="test.md", text=text, doc_type="md")
        chunks = chunk_recursive(doc, max_size=100, overlap=20)
        assert len(chunks) >= 3  # At least one per heading section
        # Check section headings are preserved
        headings = [c.section_heading for c in chunks]
        assert any(h == "Heading 1" for h in headings)
        assert any(h == "Subheading 1.1" for h in headings)
        assert any(h == "Heading 2" for h in headings)

    def test_no_headings_fallback(self):
        text = "No headings here. Just plain text that should be chunked by size."
        doc = RawDocument(source="test.txt", text=text, doc_type="txt")
        chunks = chunk_recursive(doc, max_size=30, overlap=5)
        assert len(chunks) >= 1

    def test_empty_text(self):
        text = ""
        doc = RawDocument(source="test.md", text=text, doc_type="md")
        chunks = chunk_recursive(doc, max_size=500, overlap=50)
        assert len(chunks) == 0

    def test_nested_headings(self):
        text = """# H1
Content for H1
## H2
Content for H2
### H3
Content for H3"""
        doc = RawDocument(source="test.md", text=text, doc_type="md")
        chunks = chunk_recursive(doc, max_size=200, overlap=20)
        headings = [c.section_heading for c in chunks]
        assert "H1" in headings
        assert "H2" in headings
        assert "H3" in headings


class TestChunkSemantic:
    """Tests for semantic chunking (uses embeddings)."""

    def test_basic_semantic_chunking(self):
        # This will use the mocked embeddings in tests
        text = "First sentence. Second sentence. Third sentence."
        # Note: This requires embedder - tested in integration tests
        pass


class TestChunkDataclass:
    """Tests for Chunk dataclass."""

    def test_chunk_creation(self):
        chunk = Chunk(
            id="test-id",
            text="test content",
            source="test.txt",
            chunk_index=0,
            strategy="fixed",
            char_count=12,
            section_heading="Test Heading",
        )
        assert chunk.id == "test-id"
        assert chunk.text == "test content"
        assert chunk.source == "test.txt"
        assert chunk.chunk_index == 0
        assert chunk.strategy == "fixed"
        assert chunk.char_count == 12
        assert chunk.section_heading == "Test Heading"

    def test_chunk_defaults(self):
        chunk = Chunk(
            id="test-id",
            text="test",
            source="test.txt",
            chunk_index=0,
            strategy="fixed",
            char_count=4,
        )
        assert chunk.section_heading is None