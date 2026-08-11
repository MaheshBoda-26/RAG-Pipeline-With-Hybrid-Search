"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { ArrowRight, Zap, Shield, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

const VectorSpace3D = dynamic(() => import("@/components/vector-space-3d").then((m) => m.VectorSpace3D), {
  ssr: false,
  loading: () => (
    <div className="aspect-square w-full rounded-lg bg-surface-dark-soft flex items-center justify-center" role="status" aria-label="Loading visualization">
      <div className="w-8 h-8 border-2 border-accent-teal border-t-transparent rounded-full animate-spin" />
    </div>
  ),
});

const sampleChunks = [
  { id: "1", x: -2.1, y: 0.5, z: -1.2, source: "authentication.md", strategy: "recursive", text: "API authentication uses Bearer tokens with JWT validation...", role: "dense" as const },
  { id: "2", x: 1.8, y: -0.3, z: 0.8, source: "deployment.md", strategy: "semantic", text: "Kubernetes deployment requires Helm charts and ingress configuration...", role: "reranked" as const },
  { id: "3", x: -0.5, y: 1.2, z: 2.1, source: "error_codes.md", strategy: "fixed", text: "Rate limit exceeded returns 429 with retry-after header...", role: "sparse" as const },
  { id: "4", x: 2.5, y: 0.8, z: -1.5, source: "authentication.md", strategy: "recursive", text: "Token refresh endpoint accepts valid refresh tokens...", role: "unretrieved" as const },
  { id: "5", x: -1.8, y: -1.0, z: 1.0, source: "deployment.md", strategy: "semantic", text: "Docker images built with multi-stage builds for production...", role: "unretrieved" as const },
  { id: "6", x: 0.3, y: 0.2, z: -0.8, source: "error_codes.md", strategy: "fixed", text: "Authentication failed returns 401 with WWW-Authenticate header...", role: "reranked" as const },
  { id: "7", x: -2.8, y: 1.5, z: 0.5, source: "authentication.md", strategy: "recursive", text: "OAuth 2.0 flow supports authorization code grant type...", role: "dense" as const },
  { id: "8", x: 1.2, y: -1.8, z: -0.3, source: "deployment.md", strategy: "semantic", text: "Horizontal pod autoscaler configured for CPU and memory metrics...", role: "unretrieved" as const },
  { id: "9", x: -0.8, y: 0.8, z: 1.8, source: "error_codes.md", strategy: "fixed", text: "Internal server error 500 logged with correlation ID...", role: "unretrieved" as const },
  { id: "10", x: 3.0, y: -0.5, z: 1.2, source: "authentication.md", strategy: "recursive", text: "API keys rotated quarterly with automated notifications...", role: "sparse" as const },
];

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
            >
              <span className="w-1.5 h-1.5 bg-coral rounded-full" />
              <span className="text-muted-foreground">v2.0 — Hybrid Search + LLM Reranking</span>
            </motion.div>

            <motion.h1
              id="hero-title"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="text-5xl sm:text-6xl lg:text-7xl text-ink text-balance tracking-tight leading-[1.1]"
            >
              <span className="block">Hybrid Search</span>
              <span className="block text-coral">Over Internal Docs</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.5 }}
              className="text-lg sm:text-xl text-body max-w-xl text-pretty leading-relaxed"
            >
              Production-grade RAG pipeline with dense vector search, BM25 sparse retrieval,
              reciprocal rank fusion, LLM-as-judge reranking, and grounded generation
              with verified inline citations.
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
                <span>Sub-50ms latency</span>
              </div>
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-accent-teal" />
                <span>Verified citations</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-accent-amber" />
                <span>99.9% uptime SLA</span>
              </div>
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col gap-6 lg:-ml-4"
          >
            <div className="relative overflow-hidden rounded-2xl border border-white/5 bg-surface-dark shadow-[0_32px_90px_-56px_rgba(20,20,19,0.9)]">
              <VectorSpace3D
                chunks={sampleChunks}
                query="How do I authenticate?"
                interactive={false}
                className="min-h-[360px] h-[clamp(360px,42vw,560px)] w-full"
              />
            </div>

            <div className="bg-surface-dark rounded-2xl overflow-hidden">
              <div className="flex items-center gap-3 px-4 sm:px-5 pt-4 pb-3">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-coral" />
                  <div className="w-3 h-3 rounded-full bg-accent-amber" />
                  <div className="w-3 h-3 rounded-full bg-accent-teal" />
                </div>
                <span className="text-xs text-on-dark-soft font-mono">pipeline.ask()</span>
              </div>
              <pre className="text-xs font-mono text-on-dark bg-surface-dark-soft p-5 overflow-x-auto leading-relaxed"><code>{`const pipeline = new RAGPipeline(settings);
await pipeline.ingest_directory("./docs");

const response = await pipeline.ask(
  "How do I authenticate?"
);

// Response with citations & confidence
console.log(response.answer);
console.log(response.confidence);
console.log(response.sources);`}</code></pre>
              <div className="flex items-center justify-between px-5 py-3">
                <p className="flex items-center gap-2 text-sm font-mono text-accent-teal">
                  <span className="w-2 h-2 bg-accent-teal rounded-full" />
                  confidence: 0.94
                </p>
                <p className="text-xs text-on-dark-soft">3 sources · reranked</p>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}