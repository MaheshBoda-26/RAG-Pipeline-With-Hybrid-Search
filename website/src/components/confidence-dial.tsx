"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * Confidence dial + citation hovercards.
 *
 * The dial renders the composite confidence as an animated arc with the
 * per-component bars beneath it. The refusal state is a first-class citizen:
 * a low composite renders in amber with the "say so, don't cite" message,
 * because an honest refusal is the product, not an error.
 *
 * CitedText turns `[N]` markers in an answer into hovercards showing the
 * exact cited passage — the trust promise made tangible. The hovercard text
 * is the verbatim source passage the API returned, never a generated one.
 */

interface Confidence {
  retrieval_confidence?: number;
  citation_coverage?: number | null;
  grounding_coverage?: number | null;
  completeness?: number | null;
  composite?: number;
}

function dialColor(value: number | null | undefined, refused?: boolean): string {
  if (refused) return "#e8a55a";
  if (value == null) return "#a09d96";
  if (value >= 0.6) return "#5db8a6";
  if (value >= 0.35) return "#e8a55a";
  return "#c64545";
}

export function ConfidenceDial({
  confidence,
  refused = false,
  className,
}: {
  confidence: Confidence;
  refused?: boolean;
  className?: string;
}) {
  const composite = confidence.composite ?? 0;
  const color = dialColor(composite, refused);
  const R = 34;
  const CIRC = Math.PI * R; // half-circle arc length
  const reducedMotion = true; // CSS transitions handle reduced-motion via media queries

  return (
    <div className={cn("flex items-center gap-5", className)}>
      <div className="relative h-12 w-24 shrink-0">
        <svg viewBox="0 0 96 52" className="h-full w-full" aria-label={`Composite confidence ${Math.round(composite * 100)} percent`}>
          {/* track */}
          <path
            d={`M 8 48 A ${R} ${R} 0 0 1 88 48`}
            fill="none"
            stroke="rgba(20,20,19,0.08)"
            strokeWidth={7}
            strokeLinecap="round"
          />
          {/* value arc */}
          <motion.path
            d={`M 8 48 A ${R} ${R} 0 0 1 88 48`}
            fill="none"
            stroke={color}
            strokeWidth={7}
            strokeLinecap="round"
            strokeDasharray={CIRC}
            initial={{ strokeDashoffset: CIRC }}
            animate={{ strokeDashoffset: CIRC * (1 - Math.min(Math.max(composite, 0), 1)) }}
            transition={{ duration: reducedMotion ? 0 : 0.9, ease: [0.16, 1, 0.3, 1] }}
          />
        </svg>
        <div className="absolute inset-x-0 bottom-0 text-center">
          <span className="font-mono text-lg font-semibold tabular-nums" style={{ color: "var(--color-ink)" }}>
            {Math.round(composite * 100)}
            <span className="text-xs" style={{ color: "var(--color-muted)" }}>%</span>
          </span>
        </div>
      </div>
      <div className="min-w-0 flex-1 space-y-1.5">
        {(
          [
            ["retrieval", confidence.retrieval_confidence],
            ["coverage", confidence.citation_coverage],
            ["grounding", confidence.grounding_coverage],
            ["complete", confidence.completeness],
          ] as Array<[string, number | null | undefined]>
        ).map(([label, value]) => (
          <div key={label} className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-[10px] font-mono uppercase tracking-wide" style={{ color: "var(--color-muted)" }}>
              {label}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ backgroundColor: "rgba(20,20,19,0.06)" }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.round((value ?? 0) * 100)}%` }}
                transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                className="h-full rounded-full"
                style={{ backgroundColor: value == null ? "#a39c8d" : dialColor(value, refused) }}
              />
            </div>
            <span className="w-9 shrink-0 text-right font-mono text-[10px] tabular-nums" style={{ color: "var(--color-body)" }}>
              {value == null ? "—" : `${Math.round(value * 100)}%`}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface HoverSource {
  source: string;
  text: string;
  score?: number | null;
}

/**
 * Renders answer text with [N] citation markers as interactive hovercards.
 * The hovercard shows the verbatim passage behind the citation — hovering
 * [2] shows exactly what source 2 says, so a reader can verify a claim
 * without leaving the answer.
 */
export function CitedAnswer({ answer, sources }: { answer: string; sources: HoverSource[] }) {
  const [openIdx, setOpenIdx] = React.useState<number | null>(null);
  const parts = React.useMemo(() => answer.split(/(\[\d+\])/g), [answer]);

  return (
    <div className="whitespace-pre-wrap font-mono text-sm leading-relaxed" style={{ color: "var(--color-foreground)" }}>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (!match) return <React.Fragment key={i}>{part}</React.Fragment>;
        const n = parseInt(match[1], 10);
        const src = sources[n - 1];
        if (!src) return <span key={i}>{part}</span>;
        const isOpen = openIdx === i;
        return (
          <span key={i} className="relative inline-block">
            <button
              type="button"
              onClick={() => setOpenIdx(isOpen ? null : i)}
              onMouseEnter={() => setOpenIdx(i)}
              onMouseLeave={() => setOpenIdx((cur) => (cur === i ? null : cur))}
              className="mx-0.5 inline-flex h-5 w-5 cursor-pointer items-center justify-center rounded-full align-middle text-[10px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral"
              style={{
                backgroundColor: isOpen ? "var(--color-coral)" : "color-mix(in srgb, var(--color-coral) 15%, transparent)",
                color: isOpen ? "#ffffff" : "var(--color-coral)",
              }}
              aria-label={`Citation ${n} from ${src.source}`}
            >
              {n}
            </button>
            {isOpen && (
              <motion.div
                initial={{ opacity: 0, y: 4, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
                role="tooltip"
                className="absolute bottom-7 left-1/2 z-20 w-72 -translate-x-1/2 rounded-lg border p-3 text-left shadow-xl"
                style={{
                  backgroundColor: "var(--color-canvas)",
                  borderColor: "var(--color-hairline)",
                  boxShadow: "0 18px 40px -24px rgba(20,20,19,0.45)",
                }}
              >
                <p className="mb-1 font-mono text-[10px]" style={{ color: "var(--color-coral)" }}>
                  [{n}] {src.source}
                </p>
                <p className="line-clamp-6 text-xs leading-relaxed" style={{ color: "var(--color-body)" }}>
                  {src.text}
                </p>
              </motion.div>
            )}
          </span>
        );
      })}
    </div>
  );
}
