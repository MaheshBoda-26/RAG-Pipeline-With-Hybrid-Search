"""The benchmark must stay reproducible: every golden context needs a source doc.

Without this, the golden set silently drifts away from the corpus it is written
against and the published numbers stop meaning anything.
"""
from __future__ import annotations

import json

import pytest

from scripts.build_demo_corpus import CORPUS_DIR, GOLDEN_SET, build, check_coverage


def _golden() -> list[dict]:
    return json.loads(GOLDEN_SET.read_text())


def test_generated_corpus_covers_every_golden_context():
    assert check_coverage(_golden(), build(_golden())) == []


def test_committed_corpus_covers_every_golden_context():
    """The files on disk — not just what the generator would print — must cover it."""
    documents = {}
    for path in sorted(CORPUS_DIR.glob("*.md")):
        documents[str(path)] = path.read_text()
    documents[str(CORPUS_DIR / "README.md")] = (
        (CORPUS_DIR / "README.md").read_text() if (CORPUS_DIR / "README.md").exists() else ""
    )

    assert documents, f"no corpus documents found in {CORPUS_DIR}"
    assert check_coverage(_golden(), documents) == []


@pytest.mark.parametrize("question_count", [54])
def test_golden_set_is_still_the_documented_size(question_count):
    assert len(_golden()) == question_count


def test_corpus_directory_is_ingestable_by_the_pipeline():
    """The pipeline ingests markdown; a stray binary would break `make demo`."""
    assert CORPUS_DIR.is_dir()
    for path in CORPUS_DIR.glob("*.md"):
        assert path.read_text().strip(), f"{path} is empty"
