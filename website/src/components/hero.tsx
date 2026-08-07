"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { ArrowRight, Github, Zap, Shield, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { VectorSpace3D } from "@/components/vector-space-3d";

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
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-16" aria-labelledby="hero-title">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-accent/5" aria-hidden="true" />

      <div className="absolute inset-0 opacity-5" aria-hidden="true">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-20">
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
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium border border-primary/20"
            >
              <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" />
              <span>v2.0 — Hybrid Search + LLM Reranking</span>
            </motion.div>

            <motion.h1
              id="hero-title"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="text-5xl sm:text-6xl lg:text-7xl font-semibold tracking-tight text-balance leading-[1.1]"
            >
              <span className="block">Hybrid Search</span>
              <span className="block text-primary">Over Internal Docs</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.5 }}
              className="text-lg sm:text-xl text-muted-foreground max-w-xl text-pretty leading-relaxed"
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
              <Button size="xl" asChild>
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
              className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground"
            >
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-primary" />
                <span>Sub-50ms latency</span>
              </div>
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary" />
                <span>Verified citations</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-primary" />
                <span>99.9% uptime SLA</span>
              </div>
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="relative"
          >
            <VectorSpace3D
              chunks={sampleChunks}
              query="How do I authenticate?"
              interactive={false}
              className="aspect-square max-w-md mx-auto"
            />

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7, duration: 0.5 }}
              className="absolute -bottom-8 -right-8 lg:-right-12 w-72 lg:w-80"
            >
              <div className="bg-background/90 backdrop-blur-sm rounded-xl border border-border p-5 shadow-2xl">
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-red-500" />
                    <div className="w-3 h-3 rounded-full bg-yellow-500" />
                    <div className="w-3 h-3 rounded-full bg-green-500" />
                  </div>
                  <span className="text-xs text-muted-foreground font-mono">pipeline.ask()</span>
                </div>
                <pre className="text-xs font-mono text-foreground overflow-x-auto"><code>{`const pipeline = new RAGPipeline(settings);
await pipeline.ingest_directory("./docs");

const response = await pipeline.ask(
  "How do I authenticate?"
);

// Response with citations & confidence
console.log(response.answer);
console.log(response.confidence);
console.log(response.sources);`}</code></pre>
              </div>
            </motion.div>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 0.5 }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2 animate-bounce"
          aria-hidden="true"
        >
          <svg className="w-6 h-6 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
            <path d="M12 5v14M19 12l-7 7-7-7" />
          </svg>
        </motion.div>
      </div>
    </section>
  );
}