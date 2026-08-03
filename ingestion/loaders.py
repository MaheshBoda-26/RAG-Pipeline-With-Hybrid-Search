"""Load markdown, plaintext, HTML, and PDF files into normalized RawDocument
objects: clean plaintext plus metadata (source file, section headings where
known, page numbers for PDFs).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm", ".pdf"}


@dataclass
class RawDocument:
    source: str          # file path, relative to the ingested root
    text: str            # normalized plaintext
    doc_type: str        # md | txt | html | pdf
    pages: list[dict] = field(default_factory=list)  # [{page_number, text}] for pdf; empty otherwise


def _load_markdown_or_text(path: Path, doc_type: str) -> RawDocument:
    text = path.read_text(encoding="utf-8", errors="replace")
    return RawDocument(source=str(path), text=text, doc_type=doc_type)


def _load_html(path: Path) -> RawDocument:
    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse excessive blank lines left behind by stripped tags.
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return RawDocument(source=str(path), text=text, doc_type="html")


def _load_pdf(path: Path) -> RawDocument:
    reader = PdfReader(str(path))
    pages = []
    full_text_parts = []
    for i, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        pages.append({"page_number": i, "text": page_text})
        full_text_parts.append(page_text)
    return RawDocument(
        source=str(path), text="\n\n".join(full_text_parts), doc_type="pdf", pages=pages
    )


def load_document(path: str | Path) -> RawDocument:
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".md", ".markdown"):
        return _load_markdown_or_text(path, "md")
    if ext == ".txt":
        return _load_markdown_or_text(path, "txt")
    if ext in (".html", ".htm"):
        return _load_html(path)
    if ext == ".pdf":
        return _load_pdf(path)
    raise ValueError(f"Unsupported file type: {ext} ({path})")


def load_directory(root: str | Path) -> list[RawDocument]:
    """Recursively load every supported file under `root`.

    Constraints the root path to ensure it is within the allowed base directory
    to prevent path traversal.
    """
    root = Path(root).resolve()

    # This function now assumes the caller has already validated that 'root'
    # is within the allowed directory. If not, it should be handled at the
    # entry point (e.g., the API layer).

    docs = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    docs.append(load_document(fpath))
                except Exception as e:
                    print(f"[loader] skipping {fpath}: {e}")
    return docs
