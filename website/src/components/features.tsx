"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  Database,
  GitMerge,
  Zap,
  Search,
  FileText,
  Terminal,
  Shield,
  Layers
} from "lucide-react";
import { cn } from "@/lib/utils";

const features = [
  {
    icon: Search,
    title: "Hybrid Search",
    description:
      "Dense vector embeddings (Qdrant) + sparse BM25 keyword search combined via Reciprocal Rank Fusion. Configurable weights for dense/sparse balance per query.",
    details: [
      "Qdrant embedded or remote",
      "BM25 with rank_bm25",
      "RRF k=60 default",
      "Per-query weight override",
    ],
    color: "primary",
  },
  {
    icon: GitMerge,
    title: "LLM Reranking",
    description:
      "Batched LLM-as-judge scores top 20 fused candidates in a single call. Falls back to fusion order on parse failure. Costs ~1 call per query.",
    details: [
      "Single batched API call",
      "JSON array output",
      "Graceful fallback",
      "Top-N configurable",
    ],
    color: "accent",
  },
  {
    icon: Shield,
    title: "Verified Citations",
    description:
      "Extract claims → verify against sources → compute composite confidence (retrieval × citation coverage × completeness). Refuses below threshold.",
    details: [
      "Batched verification",
      "Composite confidence score",
      "Refusal on low confidence",
      "Inline citation markers",
    ],
    color: "success",
  },
  {
    icon: Layers,
    title: "Smart Chunking",
    description:
      "Three strategies: fixed sliding window, recursive markdown-aware, semantic embedding-drift. Switchable via config — no code changes.",
    details: [
      "Fixed / Recursive / Semantic",
      "Markdown heading aware",
      "Cosine dedup (0.95)",
      "Corpus-aware index",
    ],
    color: "warning",
  },
  {
    icon: Terminal,
    title: "REST API + CLI",
    description:
      "FastAPI service with Bearer auth. Two endpoints: /v1/ask and /v1/ingest. CLI for local development. OpenAPI docs at /docs.",
    details: [
      "FastAPI + Uvicorn",
      "Bearer token auth",
      "CLI ingest/ask",
      "Auto OpenAPI spec",
    ],
    color: "secondary",
  },
  {
    icon: FileText,
    title: "Eval Ready",
    description:
      "Smoke tests with mocked LLM. Golden Q&A dataset structure defined. Chunking strategy comparison via config sweep. Phase 4 extensible.",
    details: [
      "Mocked LLM tests",
      "Deterministic embeddings",
      "Config sweep ready",
      "Golden dataset schema",
    ],
    color: "info",
  },
];

const colorMap = {
  primary: "bg-primary/10 text-primary border-primary/20",
  accent: "bg-accent/10 text-accent border-accent/20",
  success: "bg-success-500/10 text-success-500 border-success-500/20",
  warning: "bg-warning-500/10 text-warning-500 border-warning-500/20",
  secondary: "bg-secondary/10 text-secondary border-secondary/20",
  info: "bg-info-500/10 text-info-500 border-info-500/20",
};

export function Features() {
  return (
    <section
      id="features"
      className="py-24 sm:py-32 lg:py-40 bg-surface/50"
      aria-labelledby="features-title"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="text-center max-w-3xl mx-auto mb-16 lg:mb-20"
        >
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-4">
            <span className="w-1.5 h-1.5 bg-primary rounded-full" />
            <span>Core Capabilities</span>
          </span>
          <h2 id="features-title" className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance mb-6">
            Built for Production RAG
          </h2>
          <p className="text-lg sm:text-xl text-muted-foreground text-pretty leading-relaxed">
            Every component designed for reliability, observability, and scale.
            No vendor lock-in — runs on your infrastructure.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
          {features.map((feature, index) => (
            <motion.article
              key={feature.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ delay: index * 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className={cn(
                "group relative p-6 lg:p-8 rounded-xl border transition-all duration-300",
                "bg-surface border-border hover:border-primary/30 hover:shadow-xl",
                "hover:-translate-y-1"
              )}
            >
              <div
                className={cn(
                  "inline-flex items-center justify-center w-12 h-12 rounded-lg mb-6",
                  colorMap[feature.color as keyof typeof colorMap]
                )}
              >
                <feature.icon className="w-6 h-6" aria-hidden="true" />
              </div>

              <h3 className="text-xl font-semibold mb-3 group-hover:text-primary transition-colors">
                {feature.title}
              </h3>

              <p className="text-muted-foreground mb-6 leading-relaxed text-sm sm:text-base">
                {feature.description}
              </p>

              <ul className="space-y-2 text-sm text-muted-foreground/80">
                {feature.details.map((detail, i) => (
                  <li key={i} className="flex items-center gap-2 group-hover:text-foreground transition-colors">
                    <span className="w-1.5 h-1.5 rounded-full bg-current opacity-50" />
                    <span>{detail}</span>
                  </li>
                ))}
              </ul>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}