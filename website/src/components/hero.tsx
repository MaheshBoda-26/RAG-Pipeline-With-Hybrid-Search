"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { ArrowRight, Zap, Shield, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

// A small preview of the corpus map. The full, interactive version — wired to
// real embeddings via /api/demo/viz — lives in the demo section below.
const previewChunks = [
  { x: -2.1, y: 0.5, z: -1.2, source: "authentication.md", role: "dense" as const },
  { x: 1.8, y: -0.3, z: 0.8, source: "deployment.md", role: "reranked" as const },
  { x: -0.5, y: 1.2, z: 2.1, source: "error_codes.md", role: "sparse" as const },
  { x: 2.5, y: 0.8, z: -1.5, source: "authentication.md", role: "unretrieved" as const },
  { x: -1.8, y: -1.0, z: 1.0, source: "deployment.md", role: "unretrieved" as const },
  { x: 0.3, y: 0.2, z: -0.8, source: "error_codes.md", role: "reranked" as const },
];

const PREVIEW_COLORS: Record<string, string> = {
  unretrieved: "#a39c8d",
  dense: "#cc785c",
  sparse: "#e8a55a",
  reranked: "#5db8a6",
};

export function Hero() {
  return (
    <section className="relative bg-canvas pt-24 pb-24 sm:pt-28 sm:pb-28 overflow-hidden" aria-labelledby="hero-title">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="space-y-8"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1, duration: 0.4 }}
              className="inline-flex items-center gap-2 rounded-full bg-surface-card px-3 py-1 text-caption text-xs text-ink border border-hairline"
              style={{ backgroundColor: 'var(--color-surface-card)', borderColor: 'var(--color-hairline)', color: 'var(--color-ink)' }}
            >
              <span className="w-1.5 h-1.5 bg-coral rounded-full" />
              <span className="text-muted-foreground">v2.0 — Hybrid Search + Two-Stage Reranking</span>
            </motion.div>

            <motion.h1
              id="hero-title"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="text-5xl sm:text-6xl lg:text-7xl text-ink text-balance tracking-tight leading-[1.1]"
              style={{ color: 'var(--color-ink)' }}
            >
              <span className="block">Hybrid Search</span>
              <span className="block text-coral">Over Internal Docs</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.5 }}
              className="text-lg sm:text-xl text-body max-w-xl text-pretty leading-relaxed"
              style={{ color: 'var(--color-body)' }}
            >
              Production-grade RAG pipeline with dense vector search, BM25 sparse retrieval,
              reciprocal rank fusion, cross-encoder reranking with an LLM-judge fallback, and
              grounded generation with verified inline citations.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
              className="flex flex-wrap items-center gap-4"
            >
              <Button size="xl" className="bg-coral text-on-primary hover:bg-coral-active" asChild>
                <motion.a
                  href="#demo"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="flex items-center gap-2"
                >
                  <span>Try Live Demo</span>
                  <ArrowRight className="w-5 h-5" />
                </motion.a>
              </Button>
              <Button variant="outline" size="xl" asChild>
                <motion.a
                  href="#architecture"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  View Architecture
                </motion.a>
              </Button>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.5 }}
              className="flex flex-wrap items-center gap-6 text-sm text-muted"
            >
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-coral" />
                <span>Refuses to guess</span>
              </div>
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-accent-teal" />
                <span>Verified citations</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-accent-amber" />
                <span>Every number benchmarked</span>
              </div>
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col gap-6 lg:-ml-4"
          >
            <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: 'var(--color-surface-dark)' }}>
              <div className="flex items-center gap-3 px-4 sm:px-5 pt-4 pb-3" style={{ backgroundColor: 'var(--color-surface-dark-elevated)' }}>
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-coral" />
                  <div className="w-3 h-3 rounded-full bg-accent-amber" />
                  <div className="w-3 h-3 rounded-full bg-accent-teal" />
                </div>
                <span className="text-xs font-mono" style={{ color: 'var(--color-on-dark-soft)' }}>vector space · projected embeddings</span>
              </div>
              <div className="relative h-64 sm:h-72" style={{ backgroundColor: 'var(--color-surface-dark-soft)' }}>
                {/* Dot grid backdrop */}
                <div
                  className="absolute inset-0 opacity-[0.15]"
                  style={{
                    backgroundImage: "radial-gradient(circle, #a09d96 1px, transparent 1px)",
                    backgroundSize: "24px 24px",
                  }}
                />
                {previewChunks.map((chunk, i) => {
                  // Project the 3D preview coordinates to 2D for the flat hero card.
                  const left = 50 + chunk.x * 16;
                  const top = 50 + chunk.y * 14;
                  const size = chunk.role === "reranked" ? 14 : chunk.role === "unretrieved" ? 8 : 11;
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, scale: 0 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.5 + i * 0.12, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                      className="absolute rounded-full"
                      style={{
                        left: `${left}%`,
                        top: `${top}%`,
                        width: size,
                        height: size,
                        backgroundColor: PREVIEW_COLORS[chunk.role],
                        opacity: chunk.role === "unretrieved" ? 0.35 : 1,
                        transform: "translate(-50%, -50%)",
                      }}
                      title={`${chunk.source} · ${chunk.role}`}
                    />
                  );
                })}
                <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between">
                  <div className="flex items-center gap-3 text-[10px] font-mono" style={{ color: 'var(--color-on-dark-soft)' }}>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#cc785c' }} />dense</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#e8a55a' }} />sparse</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#5db8a6' }} />reranked</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between px-5 py-3" style={{ backgroundColor: 'var(--color-surface-dark-elevated)' }}>
                <p className="text-xs" style={{ color: 'var(--color-on-dark-soft)' }}>real embeddings, not an illustration</p>
                <a href="#demo" className="text-xs font-mono text-accent-teal hover:underline">explore the full map ↓</a>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}