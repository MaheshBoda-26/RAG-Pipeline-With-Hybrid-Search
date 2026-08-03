"""Evaluation framework for the RAG pipeline.

Runs the golden Q&A set against the pipeline and computes metrics:
- Answer correctness (LLM-as-judge)
- Faithfulness (are claims supported by citations)
- Retrieval relevance (hybrid vs dense-only)
- Citation accuracy
- Chunking strategy comparison
"""
from __future__ import annotations

import json
import time
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from openai import OpenAI

from config import Settings
from pipeline import RAGPipeline


@dataclass
class EvalResult:
    question: str
    expected_answer: str
    actual_answer: str
    refused: bool
    confidence: dict
    sources: list[dict]
    latency_ms: float
    # Metrics (filled by judge)
    correctness: float | None = None
    faithfulness: float | None = None
    citation_accuracy: float | None = None
    retrieval_relevance: float | None = None


@dataclass
class EvalSummary:
    total_questions: int
    answered: int
    refused: int
    avg_correctness: float | None
    avg_faithfulness: float | None
    avg_citation_accuracy: float | None
    avg_retrieval_relevance: float | None
    avg_latency_ms: float
    refusal_rate: float
    # Per-strategy breakdown (for chunking comparison)
    by_strategy: dict[str, dict] | None = None


CORRECTNESS_PROMPT = """You are evaluating the correctness of an answer to a question.
Given the expected answer and the actual answer, score correctness from 0.0 to 1.0:
- 1.0 = completely correct, matches expected answer in all material facts
- 0.5 = partially correct, some facts right but missing or wrong details
- 0.0 = completely incorrect or hallucinated

Respond with ONLY a JSON object: {"score": 0.8, "reasoning": "..."}"""

FAITHFULNESS_PROMPT = """You are evaluating faithfulness: does the answer only make claims supported by its cited sources?
Given the answer with inline citations [N] and the source passages, score faithfulness from 0.0 to 1.0:
- 1.0 = every cited claim is fully supported by its cited source(s)
- 0.5 = some claims are supported, others are not or are only loosely supported
- 0.0 = most claims are unsupported or contradicted by sources

Respond with ONLY a JSON object: {"score": 0.9, "reasoning": "..."}"""

CITATION_ACCURACY_PROMPT = """You are evaluating citation accuracy: are the inline citations pointing to the correct sources?
Given the answer with inline citations [N] and the source passages, score from 0.0 to 1.0:
- 1.0 = all citations point to sources that actually contain the cited information
- 0.5 = some citations are accurate, others point to irrelevant or wrong sources
- 0.0 = citations are largely fabricated or point to unrelated sources

Respond with ONLY a JSON object: {"score": 0.95, "reasoning": "..."}"""

RETRIEVAL_RELEVANCE_PROMPT = """You are evaluating retrieval relevance: did the system retrieve the right passages for this question?
Given the question and the retrieved source passages (with their scores), score from 0.0 to 1.0:
- 1.0 = top retrieved passages directly contain the answer
- 0.5 = relevant passages are retrieved but buried or mixed with irrelevant ones
- 0.0 = retrieved passages don't contain the answer

Respond with ONLY a JSON object: {"score": 0.8, "reasoning": "..."}"""


def load_golden_set(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def judge_score(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> tuple[float, str]:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
        return float(data["score"]), data.get("reasoning", "")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return 0.0, "Failed to parse judge response"


def run_evaluation(
    pipeline: RAGPipeline,
    golden_set: list[dict],
    settings: Settings,
    dense_only: bool = False,
) -> tuple[list[EvalResult], EvalSummary]:
    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.chat_model
    results = []

    # Save original weights if doing dense-only comparison
    orig_dense = settings.dense_weight
    orig_sparse = settings.sparse_weight
    if dense_only:
        settings.dense_weight = 1.0
        settings.sparse_weight = 0.0

    try:
        for item in golden_set:
            question = item["question"]
            expected = item["expected_answer"]

            start = time.perf_counter()
            response = pipeline.ask(question)
            latency_ms = (time.perf_counter() - start) * 1000

            # Build context for judges
            context_blocks = "\n\n".join(
                f"[{s['block']}] {s['source']}: (score: {s.get('rerank_score', 'N/A')})"
                for s in response.sources
            )

            result = EvalResult(
                question=question,
                expected_answer=expected,
                actual_answer=response.answer,
                refused=response.refused,
                confidence=response.confidence,
                sources=response.sources,
                latency_ms=latency_ms,
            )

            if not response.refused:
                # Correctness
                correctness_prompt = f"Question: {question}\n\nExpected: {expected}\n\nActual: {response.answer}"
                score, _ = judge_score(client, model, CORRECTNESS_PROMPT, correctness_prompt)
                result.correctness = score

                # Faithfulness
                faithfulness_prompt = f"Question: {question}\n\nAnswer: {response.answer}\n\nSources:\n{context_blocks}"
                score, _ = judge_score(client, model, FAITHFULNESS_PROMPT, faithfulness_prompt)
                result.faithfulness = score

                # Citation accuracy
                citation_prompt = f"Question: {question}\n\nAnswer: {response.answer}\n\nSources:\n{context_blocks}"
                score, _ = judge_score(client, model, CITATION_ACCURACY_PROMPT, citation_prompt)
                result.citation_accuracy = score

                # Retrieval relevance
                retrieval_prompt = f"Question: {question}\n\nRetrieved sources:\n{context_blocks}"
                score, _ = judge_score(client, model, RETRIEVAL_RELEVANCE_PROMPT, retrieval_prompt)
                result.retrieval_relevance = score

            results.append(result)
            print(f"  ✓ {question[:60]}... (latency: {latency_ms:.0f}ms, refused: {response.refused})")

    finally:
        # Restore original weights
        settings.dense_weight = orig_dense
        settings.sparse_weight = orig_sparse

    # Compute summary
    answered = [r for r in results if not r.refused]
    refused = [r for r in results if r.refused]

    def avg(values: list[float | None]) -> float | None:
        valid = [v for v in values if v is not None]
        return statistics.mean(valid) if valid else None

    summary = EvalSummary(
        total_questions=len(results),
        answered=len(answered),
        refused=len(refused),
        avg_correctness=avg([r.correctness for r in answered]),
        avg_faithfulness=avg([r.faithfulness for r in answered]),
        avg_citation_accuracy=avg([r.citation_accuracy for r in answered]),
        avg_retrieval_relevance=avg([r.retrieval_relevance for r in answered]),
        avg_latency_ms=statistics.mean([r.latency_ms for r in results]) if results else 0,
        refusal_rate=len(refused) / len(results) if results else 0,
    )

    return results, summary


def run_chunking_comparison(
    golden_set: list[dict],
    settings: Settings,
    strategies: list[str] = None,
) -> dict[str, tuple[list[EvalResult], EvalSummary]]:
    """Run evaluation once per chunking strategy."""
    strategies = strategies or ["fixed", "recursive", "semantic"]
    results = {}

    for strategy in strategies:
        print(f"\n=== Evaluating chunking strategy: {strategy} ===")
        settings.chunking_strategy = strategy
        pipeline = RAGPipeline(settings)
        # Need to re-ingest for each strategy
        # Assuming sample_docs is the test corpus
        pipeline.ingest_directory(settings.allowed_ingest_root)

        eval_results, summary = run_evaluation(pipeline, golden_set, settings)
        results[strategy] = (eval_results, summary)
        print(f"  Correctness: {summary.avg_correctness:.3f}, Faithfulness: {summary.avg_faithfulness:.3f}")

    return results


def export_results(
    results: list[EvalResult],
    summary: EvalSummary,
    output_path: str,
    comparison: dict[str, tuple[list[EvalResult], EvalSummary]] = None,
) -> None:
    """Export detailed results and summary to JSON."""
    data = {
        "summary": asdict(summary),
        "results": [asdict(r) for r in results],
    }
    if comparison:
        data["chunking_comparison"] = {
            strat: {"summary": asdict(summ), "results": [asdict(r) for r in res]}
            for strat, (res, summ) in comparison.items()
        }

    Path(output_path).write_text(json.dumps(data, indent=2))
    print(f"\nResults exported to {output_path}")


def print_summary(summary: EvalSummary) -> None:
    print(f"\n{'='*50}")
    print(f"EVALUATION SUMMARY")
    print(f"{'='*50}")
    print(f"Total questions:  {summary.total_questions}")
    print(f"Answered:         {summary.answered}")
    print(f"Refused:          {summary.refused} ({summary.refusal_rate:.1%})")
    print(f"Avg latency:      {summary.avg_latency_ms:.0f}ms")
    print(f"")
    print(f"Correctness:      {summary.avg_correctness:.3f}" if summary.avg_correctness else "Correctness:      N/A")
    print(f"Faithfulness:     {summary.avg_faithfulness:.3f}" if summary.avg_faithfulness else "Faithfulness:     N/A")
    print(f"Citation accuracy: {summary.avg_citation_accuracy:.3f}" if summary.avg_citation_accuracy else "Citation accuracy: N/A")
    print(f"Retrieval relevance: {summary.avg_retrieval_relevance:.3f}" if summary.avg_retrieval_relevance else "Retrieval relevance: N/A")
    print(f"{'='*50}")