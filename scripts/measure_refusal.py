#!/usr/bin/env python3
"""Measure the refusal gate on questions the corpus cannot answer.

A retrieval system is only trustworthy if it says "I don't know" when the
sources do not contain the answer. This runs the unanswerable set through the
real pipeline and reports:

- refusal rate: how often the pipeline refused instead of answering
- false-citation rate: how often it answered anyway *with* citations, which is
  the dangerous failure (an ungrounded answer that looks grounded)
- confidence distribution for refusals vs non-refusals, so the gate threshold
  can be tuned against data instead of intuition

Usage:
    USE_SUPABASE=false QDRANT_PATH=./qdrant_data_eval \\
        python scripts/measure_refusal.py --output /tmp/refusals.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Settings  # noqa: E402
from pipeline import RAGPipeline  # noqa: E402
from tests.eval.runner import describe_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Refusal-gate measurement")
    parser.add_argument("--set", default="tests/eval/unanswerable_set.json")
    parser.add_argument("--output", default="/tmp/refusals.json")
    parser.add_argument("--existing", default="tests/eval/results.json",
                        help="A results file to read the answered-question confidence baseline from")
    args = parser.parse_args()

    questions = json.loads(Path(args.set).read_text())
    settings = Settings()
    pipeline = RAGPipeline(settings)
    print("CONFIG: " + json.dumps(describe_config(settings), sort_keys=True))

    rows = []
    for item in questions:
        response = pipeline.ask(item["question"])
        rows.append({
            "question": item["question"],
            "refused": response.refused,
            "refusal_reason": response.refusal_reason,
            "answered_with_citations": bool(response.sources) and not response.refused,
            "confidence": response.confidence,
            "answer": response.answer,
            "timings": response.timings,
        })
        status = "refused" if response.refused else "ANSWERED"
        print(f"  {status:8s} | {item['question'][:70]}")

    refused = [r for r in rows if r["refused"]]
    answered = [r for r in rows if not r["refused"]]
    false_citation = [r for r in answered if r["answered_with_citations"]]

    def mean(values):
        return statistics.mean(values) if values else None

    refusal_confidences = [r["confidence"].get("composite") for r in refused if r["confidence"].get("composite") is not None]
    answered_confidences = [r["confidence"].get("composite") for r in answered if r["confidence"].get("composite") is not None]

    summary = {
        "questions": len(rows),
        "refused": len(refused),
        "refusal_rate": len(refused) / len(rows) if rows else None,
        "false_citation_rate": len(false_citation) / len(rows) if rows else 0.0,
        "mean_composite_when_refused": mean(refusal_confidences),
        "mean_composite_when_answered": mean(answered_confidences),
        "threshold": settings.min_retrieval_confidence,
        "config": describe_config(settings),
    }
    Path(args.output).write_text(json.dumps({"summary": summary, "results": rows}, indent=2))

    print("\n" + "=" * 52)
    print("REFUSAL GATE")
    print("=" * 52)
    print(f"Unanswerable questions:      {summary['questions']}")
    print(f"Refused:                     {summary['refused']} ({summary['refusal_rate']:.0%})")
    print(f"Answered with citations:     {len(false_citation)} ({summary['false_citation_rate']:.0%})")
    print(f"Mean composite | refused:    {summary['mean_composite_when_refused']}")
    print(f"Mean composite | answered:   {summary['mean_composite_when_answered']}")
    print(f"Gate threshold:              {summary['threshold']}")
    print(f"\nWritten to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
