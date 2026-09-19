"use client";

import * as React from "react";
import { motion } from "framer-motion";

/**
 * Benchmark band — the CI numbers, rendered as data.
 *
 * Reads tests/eval/results.json, the file `make eval` and the CI eval job
 * regenerate. The site cannot drift from the benchmark: both read the same
 * artifact. When the file is missing (API repo not built) the band renders
 * nothing rather than showing stale or invented numbers.
 */

interface ResultsFile {
  summary: {
    total_questions: number;
    answered: number;
    refused: number;
    refusal_rate: number;
    avg_correctness?: number | null;
    avg_faithfulness?: number | null;
    avg_citation_accuracy?: number | null;
    avg_retrieval_relevance?: number | null;
    avg_latency_ms?: number | null;
    recall_at_1?: number | null;
    recall_at_3?: number | null;
    recall_at_5?: number | null;
    mrr?: number | null;
    ndcg_at_5?: number | null;
  };
}

const fmt = (v: number | null | undefined, digits = 3) =>
  v == null ? "—" : v.toFixed(digits);

export function BenchmarkBand() {
  const [summary, setSummary] = React.useState<ResultsFile["summary"] | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    fetch("/eval/results.json", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("not found"))))
      .then((data: ResultsFile) => {
        if (!cancelled) setSummary(data.summary);
      })
      .catch(() => {
        /* leave the band hidden — no invented numbers */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!summary) return null;

  const headline = [
    { label: "Recall@1", value: fmt(summary.recall_at_1) },
    { label: "Recall@5", value: fmt(summary.recall_at_5) },
    { label: "MRR", value: fmt(summary.mrr) },
    { label: "NDCG@5", value: fmt(summary.ndcg_at_5) },
    { label: "Citation accuracy", value: fmt(summary.avg_citation_accuracy) },
    { label: "Faithfulness", value: fmt(summary.avg_faithfulness) },
  ];

  return (
    <section className="py-16 sm:py-20" style={{ backgroundColor: "var(--color-surface-dark)" }} aria-label="Benchmark results">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="mb-8 flex flex-wrap items-baseline justify-between gap-3">
            <div>
              <p className="mb-1 font-mono text-[11px] uppercase tracking-widest" style={{ color: "#e8a55a" }}>
                measured, not claimed
              </p>
              <h2 className="text-2xl font-semibold sm:text-3xl" style={{ color: "var(--color-on-dark)" }}>
                {summary.total_questions} questions · judged · reproducible
              </h2>
            </div>
            <a
              href="https://github.com/MaheshBoda-26/RAG-Pipeline-With-Hybrid-Search/blob/main/docs/benchmarks.md"
              className="font-mono text-xs hover:underline"
              style={{ color: "#5db8a6" }}
            >
              methodology + raw numbers ↗
            </a>
          </div>

          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl sm:grid-cols-3 lg:grid-cols-6" style={{ backgroundColor: "rgba(250,249,245,0.08)" }}>
            {headline.map((item, i) => (
              <motion.div
                key={item.label}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06, duration: 0.4 }}
                className="px-4 py-5"
                style={{ backgroundColor: "var(--color-surface-dark-elevated)" }}
              >
                <p className="font-mono text-2xl font-semibold tabular-nums" style={{ color: "#5db8a6" }}>
                  {item.value}
                </p>
                <p className="mt-1 text-[11px] font-mono uppercase tracking-wide" style={{ color: "var(--color-on-dark-soft)" }}>
                  {item.label}
                </p>
              </motion.div>
            ))}
          </div>

          <p className="mt-4 text-xs leading-relaxed" style={{ color: "var(--color-on-dark-soft)" }}>
            Retrieval metrics are judge-free — computed against the golden passage each question must
            surface, so retrieval failures and generation failures are separable. Refusals:{" "}
            {summary.refused} of {summary.total_questions} ({(summary.refusal_rate * 100).toFixed(1)}%) on
            this answerable set; the refusal gate itself is measured separately on unanswerable questions.
            Regenerate with <code className="font-mono">make eval</code>.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
