"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { VectorSpace3D } from "@/components/vector-space-3d";

/**
 * Vector-space explorer — the real corpus, really embedded.
 *
 * Fetches /api/demo/viz (backed by GET /v1/demo/viz), which returns the
 * stored chunk embeddings projected to 3D coordinates by the backend. The
 * points on screen ARE the index: nothing here invents sample coordinates.
 * When the API is offline the section says so instead of showing fake data.
 */

interface VizChunk {
  id: string;
  x: number;
  y: number;
  z: number;
  source: string;
  strategy: string;
  section_heading?: string | null;
  text: string;
  role: "unretrieved" | "dense" | "sparse" | "reranked" | "query";
}

interface VizResponse {
  chunks: VizChunk[];
  total_chunks: number;
  truncated: boolean;
}

export function VectorSpaceExplorer() {
  const [chunks, setChunks] = React.useState<VizChunk[] | null>(null);
  const [total, setTotal] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/demo/viz")
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || "API unavailable");
        return res.json();
      })
      .then((data: VizResponse) => {
        if (cancelled) return;
        setChunks(data.chunks);
        setTotal(data.total_chunks);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_280px]">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative h-[420px] overflow-hidden rounded-2xl border"
        style={{ borderColor: "var(--color-hairline)", backgroundColor: "var(--color-surface-dark)" }}
      >
        {error ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
            <p className="text-sm font-medium" style={{ color: "var(--color-on-dark-soft)" }}>
              Vector space unavailable — the API must be running on localhost:8000.
            </p>
            <p className="text-xs font-mono" style={{ color: "var(--color-on-dark-soft)" }}>
              make api → then reload
            </p>
          </div>
        ) : chunks === null ? (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-coral border-t-transparent" />
            <p className="text-xs font-mono" style={{ color: "var(--color-on-dark-soft)" }}>
              projecting stored embeddings…
            </p>
          </div>
        ) : (
          <VectorSpace3D chunks={chunks} interactive height="100%" />
        )}
      </motion.div>

      <div className="space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ delay: 0.1, duration: 0.5 }}
          className="rounded-xl border p-5"
          style={{ borderColor: "var(--color-hairline)", backgroundColor: "var(--color-surface)" }}
        >
          <p className="mb-1 text-xs font-mono uppercase tracking-widest" style={{ color: "var(--color-coral)" }}>
            real embeddings
          </p>
          <p className="text-sm leading-relaxed" style={{ color: "var(--color-body)" }}>
            Every point is an indexed chunk, positioned from its actual stored
            embedding — same vectors the dense retrieval leg searches. Nearby
            points are semantically near; that is the search.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ delay: 0.15, duration: 0.5 }}
          className="rounded-xl border p-5"
          style={{ borderColor: "var(--color-hairline)", backgroundColor: "var(--color-surface)" }}
        >
          <p className="mb-3 font-mono text-[11px] uppercase tracking-widest" style={{ color: "var(--color-muted)" }}>
            legend
          </p>
          <div className="space-y-2 text-xs" style={{ color: "var(--color-body)" }}>
            <p className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "#5db8a6" }} /> reranked finalists
            </p>
            <p className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "#cc785c" }} /> dense matches
            </p>
            <p className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "#e8a55a" }} /> sparse matches
            </p>
            <p className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full opacity-40" style={{ backgroundColor: "#a39c8d" }} /> indexed, unretrieved
            </p>
          </div>
          {total > 0 && (
            <p className="mt-4 font-mono text-[11px]" style={{ color: "var(--color-muted)" }}>
              {chunks?.length === total ? `${total} chunks` : `${chunks?.length} of ${total} chunks`}
            </p>
          )}
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
          className="text-xs leading-relaxed"
          style={{ color: "var(--color-muted)" }}
        >
          Drag to orbit, scroll to zoom, hover a point for its passage. Ask a
          question below and the retrieved set lights up against this map.
        </motion.p>
      </div>
    </div>
  );
}
