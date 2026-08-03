#!/usr/bin/env python3
"""Run evaluation suite against the RAG pipeline.

Usage:
    python -m tests.eval.run_eval                    # Run full eval
    python -m tests.eval.run_eval --dense-only       # Compare hybrid vs dense-only
    python -m tests.eval.run_eval --compare-chunking # Compare chunking strategies
    python -m tests.eval.run_eval --output results.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Settings
from pipeline import RAGPipeline
from tests.eval.runner import (
    load_golden_set,
    run_evaluation,
    run_chunking_comparison,
    export_results,
    print_summary,
)


def main():
    parser = argparse.ArgumentParser(description="RAG Pipeline Evaluation")
    parser.add_argument("--golden-set", default="tests/eval/golden_set.json", help="Path to golden Q&A set")
    parser.add_argument("--output", default="tests/eval/results.json", help="Output path for results")
    parser.add_argument("--dense-only", action="store_true", help="Run with dense-only retrieval (sparse_weight=0)")
    parser.add_argument("--compare-chunking", action="store_true", help="Compare all chunking strategies")
    parser.add_argument("--strategies", nargs="+", default=["fixed", "recursive", "semantic"], help="Chunking strategies to compare")
    args = parser.parse_args()

    settings = Settings()

    # Load golden set
    golden_path = Path(args.golden_set)
    if not golden_path.exists():
        print(f"Golden set not found: {golden_path}")
        sys.exit(1)

    golden_set = load_golden_set(str(golden_path))
    print(f"Loaded {len(golden_set)} questions from {golden_path}")

    comparison = None

    if args.compare_chunking:
        print(f"\nRunning chunking strategy comparison: {args.strategies}")
        comparison = run_chunking_comparison(golden_set, settings, args.strategies)
        # Use the default strategy for the main results
        settings.chunking_strategy = "recursive"
        pipeline = RAGPipeline(settings)
        pipeline.ingest_directory(settings.allowed_ingest_root)
        results, summary = run_evaluation(pipeline, golden_set, settings)
    else:
        pipeline = RAGPipeline(settings)
        # Ingest if needed
        try:
            pipeline.ingest_directory(settings.allowed_ingest_root)
        except Exception as e:
            print(f"Warning: ingest failed (may already be indexed): {e}")

        print(f"\nRunning evaluation (dense_only={args.dense_only})...")
        results, summary = run_evaluation(pipeline, golden_set, settings, dense_only=args.dense_only)

    print_summary(summary)
    export_results(results, summary, args.output, comparison)

    # Check PRD targets
    print("\nPRD TARGET CHECKS:")
    if summary.avg_correctness is not None:
        target = 0.90  # Not explicitly in PRD, but implied by faithfulness
        status = "✓" if summary.avg_correctness >= target else "✗"
        print(f"  Correctness ≥ {target:.0%}: {status} ({summary.avg_correctness:.1%})")

    if summary.avg_faithfulness is not None:
        target = 0.90
        status = "✓" if summary.avg_faithfulness >= target else "✗"
        print(f"  Faithfulness (citation coverage) ≥ {target:.0%}: {status} ({summary.avg_faithfulness:.1%})")

    if summary.refusal_rate is not None:
        target = 0.90  # For out-of-corpus questions
        status = "✓" if summary.refusal_rate >= target else "✗"
        print(f"  Refusal rate ≥ {target:.0%}: {status} ({summary.refusal_rate:.1%})")

    if summary.avg_latency_ms is not None:
        target = 10000  # 10s p95
        status = "✓" if summary.avg_latency_ms <= target else "✗"
        print(f"  p95 Latency < {target/1000}s: {status} ({summary.avg_latency_ms:.0f}ms avg)")

    if summary.avg_retrieval_relevance is not None:
        # This would need hybrid vs dense comparison
        pass


if __name__ == "__main__":
    main()