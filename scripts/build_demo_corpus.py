#!/usr/bin/env python3
"""Materialise the demo corpus that the golden set is written against.

The golden set (``tests/eval/golden_set.json``) asks about a fictional "Aegis
API". Those documents were never committed, which made the benchmark impossible
to reproduce. This script derives the corpus from each item's ``context`` field
(the ground-truth passage) so retrieval and evaluation share one source of
truth, and fails loudly if any golden context is not covered.

Usage:
    python scripts/build_demo_corpus.py            # write sample_docs/aegis/
    python scripts/build_demo_corpus.py --check    # verify coverage only
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

GOLDEN_SET = Path("tests/eval/golden_set.json")
CORPUS_DIR = Path("sample_docs/aegis")

# Keyword -> document. First match wins; order matters.
TOPICS: list[tuple[str, tuple[str, ...]]] = [
    ("authentication", ("auth", "oauth", "api key", "token", "credential", "workspace")),
    ("rate_limits", ("rate limit", "quota", "429", "throughput", "burst")),
    ("error_codes", ("error", "4xx", "5xx", "status code", "retry", "idempot")),
    ("deployment", ("deploy", "kubernetes", "helm", "docker", "region", "self-host", "on-prem")),
    ("webhooks", ("webhook", "callback", "event", "signature", "delivery")),
    ("data_api", ("pagination", "page", "cursor", "batch", "filter", "sort", "upload", "document")),
]

HEADINGS = {
    "authentication": "Aegis API — Authentication",
    "rate_limits": "Aegis API — Rate Limits and Quotas",
    "error_codes": "Aegis API — Errors and Retries",
    "deployment": "Aegis API — Deployment and Environments",
    "webhooks": "Aegis API — Webhooks and Events",
    "data_api": "Aegis API — Data, Pagination and Documents",
    "general": "Aegis API — Overview",
}


def classify(item: dict) -> str:
    haystack = f"{item['question']} {item['context']}".lower()
    for topic, keywords in TOPICS:
        if any(keyword in haystack for keyword in keywords):
            return topic
    return "general"


def slug(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in " -" else " " for ch in text.lower())
    words = [word for word in cleaned.split() if word not in {"what", "how", "does", "the", "a", "an", "is", "are", "do", "you", "your", "of", "to", "for", "in", "and", "it"}]
    return "-".join(words[:6]) or "section"


def build(golden: list[dict]) -> dict[str, str]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in golden:
        grouped[classify(item)].append(item)

    documents: dict[str, str] = {}
    for topic, items in grouped.items():
        lines = [f"# {HEADINGS[topic]}", ""]
        lines.append(
            "Reference documentation for the Aegis platform API. "
            "Every statement below is normative for the current API version."
        )
        lines.append("")
        for item in items:
            lines.append(f"## {item['question'].rstrip('?')}")
            lines.append("")
            lines.append(item["context"].strip())
            lines.append("")
        documents[f"{topic}.md"] = "\n".join(lines).rstrip() + "\n"
    return documents


def check_coverage(golden: list[dict], documents: dict[str, str]) -> list[str]:
    """Return golden contexts that are missing from the corpus."""
    blob = "\n".join(documents.values())
    return [item["context"] for item in golden if item["context"].strip() not in blob]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify coverage without writing")
    parser.add_argument("--golden-set", default=str(GOLDEN_SET))
    args = parser.parse_args(argv)

    golden = json.loads(Path(args.golden_set).read_text())
    documents = build(golden)
    missing = check_coverage(golden, documents)

    if missing:
        print(f"FAIL: {len(missing)} golden contexts are not covered:", file=sys.stderr)
        for context in missing[:5]:
            print(f"  - {context[:90]}", file=sys.stderr)
        return 1

    if args.check:
        print(f"OK: all {len(golden)} golden contexts are covered by {len(documents)} documents")
        return 0

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(documents.items()):
        (CORPUS_DIR / name).write_text(content)
        print(f"wrote {CORPUS_DIR / name}")
    print(f"OK: {len(golden)} golden contexts covered across {len(documents)} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
