"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Pipeline Console — the real pipeline, executing live.
 *
 * Every number shown comes from one actual `ask()` run on the backend
 * (POST /api/demo/pipeline): per-stage wall-clock timings, the dense and
 * sparse retrieval lanes, fusion, rerank order and the confidence breakdown.
 * There is no mock path and no client-side simulation: when the backend
 * refuses, the console shows the refusal.
 */

interface TraceSource {
  block: number;
  source: string;
  text?: string;
  fused_score?: number | null;
  rerank_score?: number | null;
  dense_score?: number | null;
}

interface PipelineTrace {
  question: string;
  answer: string;
  sources: TraceSource[];
  confidence: {
    retrieval_confidence?: number;
    citation_coverage?: number | null;
    grounding_coverage?: number | null;
    completeness?: number | null;
    composite?: number;
  };
  refused?: boolean;
  refusal_reason?: string | null;
  timings: Record<string, number>;
  total_ms: number;
  lanes?: Record<string, Array<Record<string, unknown>>>;
}

const STAGE_LABELS: Record<string, string> = {
  transform_query: "01 · TRANSFORM",
  embed_query: "02 · EMBED",
  retrieve: "03 · RETRIEVE",
  rerank: "04 · RERANK",
  generate: "05 · GENERATE",
  extract_claims: "06 · CLAIMS",
  verify_and_score: "07 · VERIFY",
};

// Stage colors from the design system: amber ingest-side, coral dense,
// teal sparse, deep green rerank — used consistently across console and map.
const STAGE_COLORS: Record<string, string> = {
  transform_query: "#e8a55a",
  embed_query: "#e8a55a",
  retrieve: "#cc785c",
  rerank: "#5db8a6",
  generate: "#8fbc8f",
  extract_claims: "#a09d96",
  verify_and_score: "#a09d96",
};

const TOTAL_STAGE_SPAN = 7;

function ms(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(2)} s`;
  return `${value.toFixed(0)} ms`;
}

function pct(value: number | null | undefined): string {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

function StageRow({ stage, msValue, maxMs, delay }: { stage: string; msValue: number; maxMs: number; delay: number }) {
  const width = maxMs > 0 ? Math.max(2, (msValue / maxMs) * 100) : 2;
  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="flex items-center gap-3"
    >
      <span className="w-32 shrink-0 text-[11px] font-mono tracking-wide" style={{ color: "var(--color-on-dark-soft)" }}>
        {STAGE_LABELS[stage] ?? stage}
      </span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full" style={{ backgroundColor: "rgba(250,249,245,0.08)" }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${width}%` }}
          transition={{ delay: delay + 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="h-full rounded-full"
          style={{ backgroundColor: STAGE_COLORS[stage] ?? "#cc785c" }}
        />
      </div>
      <span className="w-16 shrink-0 text-right text-[11px] font-mono" style={{ color: "var(--color-on-dark)" }}>
        {ms(msValue)}
      </span>
    </motion.div>
  );
}

function ConfidenceBars({ confidence }: { confidence: PipelineTrace["confidence"] }) {
  const rows: Array<{ label: string; value: number | null | undefined }> = [
    { label: "retrieval", value: confidence.retrieval_confidence },
    { label: "citation coverage", value: confidence.citation_coverage },
    { label: "grounding", value: confidence.grounding_coverage },
    { label: "completeness", value: confidence.completeness },
    { label: "composite", value: confidence.composite },
  ];
  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <motion.div
          key={row.label}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 + i * 0.08 }}
          className="flex items-center gap-3"
        >
          <span className="w-32 shrink-0 text-[11px] font-mono" style={{ color: "var(--color-on-dark-soft)" }}>
            {row.label}
          </span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full" style={{ backgroundColor: "rgba(250,249,245,0.08)" }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${Math.round((row.value ?? 0) * 100)}%` }}
              transition={{ delay: 0.3 + i * 0.08, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="h-full rounded-full"
              style={{
                backgroundColor:
                  row.value == null ? "#a09d96" : row.value >= 0.6 ? "#5db8a6" : row.value >= 0.35 ? "#e8a55a" : "#c64545",
              }}
            />
          </div>
          <span className="w-12 shrink-0 text-right text-[11px] font-mono" style={{ color: "var(--color-on-dark)" }}>
            {pct(row.value)}
          </span>
        </motion.div>
      ))}
    </div>
  );
}

export function PipelineConsole({ trace }: { trace: PipelineTrace | null }) {
  if (!trace) return null;

  const stages = Object.entries(trace.timings);
  const maxMs = Math.max(...stages.map(([, v]) => v), 1);
  const stageDelay = Math.min(0.35, 2.4 / Math.max(stages.length, 1));

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="overflow-hidden rounded-xl"
      style={{ backgroundColor: "var(--color-surface-dark)" }}
      aria-label="Live pipeline execution trace"
    >
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ backgroundColor: "var(--color-surface-dark-elevated)" }}
      >
        <span className="flex items-center gap-2 text-xs font-mono" style={{ color: "var(--color-on-dark-soft)" }}>
          <Activity className="h-3.5 w-3.5 text-accent-teal" />
          pipeline.ask() — live trace
        </span>
        <span className="text-[11px] font-mono" style={{ color: "var(--color-on-dark-soft)" }}>
          total {ms(trace.total_ms)}
        </span>
      </div>

      <div className="space-y-6 p-5">
        {/* Stage timings */}
        <div className="space-y-2.5">
          {stages.map(([stage, msValue], i) => (
            <StageRow key={stage} stage={stage} msValue={msValue} maxMs={maxMs} delay={i * stageDelay} />
          ))}
        </div>

        {/* Retrieval lanes */}
        {trace.sources.length > 0 && (
          <div>
            <p className="mb-2 text-[11px] font-mono uppercase tracking-widest" style={{ color: "var(--color-on-dark-soft)" }}>
              retrieval lanes → rerank order
            </p>
            <div className="space-y-1.5">
              {trace.sources.map((s, i) => (
                <motion.div
                  key={s.block}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + i * 0.08 }}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-[11px] font-mono"
                  style={{ backgroundColor: "var(--color-surface-dark-soft)" }}
                >
                  <span
                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px]"
                    style={{ backgroundColor: "#5db8a6", color: "#141413" }}
                  >
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate" style={{ color: "var(--color-on-dark)" }}>
                    {s.source}
                  </span>
                  <span className="shrink-0" style={{ color: "#cc785c" }} title="dense cosine">
                    d {s.dense_score != null ? s.dense_score.toFixed(2) : "—"}
                  </span>
                  <span className="shrink-0" style={{ color: "#e8a55a" }} title="fused RRF score">
                    f {s.fused_score != null ? s.fused_score.toFixed(3) : "—"}
                  </span>
                  <span className="shrink-0" style={{ color: "#5db8a6" }} title="rerank score 0–10">
                    r {s.rerank_score != null ? s.rerank_score.toFixed(2) : "—"}
                  </span>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* Confidence breakdown */}
        <div>
          <p className="mb-2 text-[11px] font-mono uppercase tracking-widest" style={{ color: "var(--color-on-dark-soft)" }}>
            confidence breakdown
          </p>
          <ConfidenceBars confidence={trace.confidence} />
        </div>

        {/* Refusal state — designed as a first-class citizen */}
        <AnimatePresence>
          {trace.refused && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-start gap-3 rounded-md border p-4"
              style={{ borderColor: "#e8a55a55", backgroundColor: "rgba(232,165,90,0.08)" }}
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#e8a55a" }} />
              <div>
                <p className="text-xs font-medium" style={{ color: "#e8a55a" }}>
                  The pipeline refused rather than answer.
                </p>
                <p className="mt-1 text-[11px] font-mono" style={{ color: "var(--color-on-dark-soft)" }}>
                  {trace.refusal_reason ?? "low confidence"}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
