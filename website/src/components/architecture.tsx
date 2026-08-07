"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { ChevronDown, Database, Cpu, Brain, FileText, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const stages = [
  {
    number: "01",
    title: "Ingestion",
    icon: Database,
    components: [
      { name: "loaders.py", desc: "Multi-format → plaintext (PDF, MD, TXT, HTML)" },
      { name: "chunking.py", desc: "Fixed / Recursive / Semantic strategies" },
      { name: "dedup.py", desc: "Corpus-aware cosine similarity > 0.95" },
    ],
    color: "primary",
  },
  {
    number: "02",
    title: "Retrieval",
    icon: Cpu,
    components: [
      { name: "embeddings.py", desc: "text-embedding-3-small (1536-dim)" },
      { name: "vector_store.py", desc: "Qdrant dense top-10" },
      { name: "sparse.py", desc: "BM25 top-10 keyword search" },
      { name: "fusion.py", desc: "Reciprocal Rank Fusion k=60" },
      { name: "reranker.py", desc: "LLM judge top-20 → top-5" },
    ],
    color: "accent",
  },
  {
    number: "03",
    title: "Generation",
    icon: Brain,
    components: [
      { name: "generate.py", desc: "Grounded answer + context assembly" },
      { name: "citations.py", desc: "Extract → Verify → Composite score" },
      { name: "prompts.py", desc: "System prompts & templates" },
    ],
    color: "success",
  },
];

const colorStyles = {
  primary: "bg-primary/10 text-primary border-primary/20",
  accent: "bg-accent/10 text-accent border-accent/20",
  success: "bg-success-500/10 text-success-500 border-success-500/20",
};

export function Architecture() {
  return (
    <section
      id="architecture"
      className="py-24 sm:py-32 lg:py-40"
      aria-labelledby="arch-title"
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
            <span>System Design</span>
          </span>
          <h2 id="arch-title" className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance mb-6">
            Architecture Overview
          </h2>
          <p className="text-lg sm:text-xl text-muted-foreground text-pretty leading-relaxed">
            Modular pipeline with clear stage boundaries. Each component swappable
            via config — no hard dependencies between stages.
          </p>
        </motion.div>

        <div className="space-y-8 lg:space-y-12">
          {stages.map((stage, stageIndex) => (
            <motion.div
              key={stage.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ delay: stageIndex * 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="relative"
            >
              <div className="grid lg:grid-cols-[1fr_auto_1fr] gap-8 lg:gap-12 items-start">
                <div className="lg:order-1 lg:text-right lg:pr-8">
                  <div className="flex items-center justify-end lg:justify-end gap-3 mb-6">
                    <span className="text-3xl font-mono font-bold text-muted-foreground/30">
                      {stage.number}
                    </span>
                    <div className="text-right">
                      <div
                        className={cn(
                          "inline-flex items-center justify-center w-12 h-12 rounded-lg mb-2",
                          colorStyles[stage.color as keyof typeof colorStyles]
                        )}
                      >
                        <stage.icon className="w-6 h-6" aria-hidden="true" />
                      </div>
                      <h3 className="text-2xl font-semibold">{stage.title}</h3>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {stage.components.map((comp, compIndex) => (
                      <motion.div
                        key={comp.name}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: stageIndex * 0.1 + compIndex * 0.05, duration: 0.4 }}
                        className={cn(
                          "p-4 rounded-lg border border-border bg-surface/50",
                          "hover:border-primary/30 hover:shadow-lg transition-all duration-300",
                          "group"
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center flex-shrink-0 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                            <FileText className="w-4 h-4" />
                          </div>
                          <div className="text-left">
                            <code className="font-mono text-sm font-medium text-foreground">{comp.name}</code>
                            <p className="text-sm text-muted-foreground mt-0.5">{comp.desc}</p>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>

                {stageIndex < stages.length - 1 && (
                  <div className="lg:order-2 flex flex-col items-center lg:hidden my-8">
                    <motion.div
                      initial={{ scaleY: 0 }}
                      animate={{ scaleY: 1 }}
                      transition={{ delay: stageIndex * 0.2 + 0.5, duration: 0.5 }}
                      className="w-0.5 h-24 bg-gradient-to-b from-primary/30 to-primary"
                    />
                    <ChevronDown className="w-5 h-5 text-muted-foreground" />
                    <motion.div
                      initial={{ scaleY: 0 }}
                      animate={{ scaleY: 1 }}
                      transition={{ delay: stageIndex * 0.2 + 0.6, duration: 0.5 }}
                      className="w-0.5 h-24 bg-gradient-to-b from-primary to-primary/30"
                    />
                  </div>
                )}

                <div className="lg:order-3 lg:pl-8 relative">
                  <div className="hidden lg:block absolute left-0 top-10 bottom-0 w-0.5 bg-gradient-to-b from-primary/20 via-primary to-primary/20" />
                  <div className="relative z-10">
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95 }}
                      whileInView={{ opacity: 1, scale: 1 }}
                      viewport={{ once: true, amount: 0.2 }}
                      transition={{ delay: stageIndex * 0.1 + 0.3, duration: 0.5 }}
                      className="bg-surface border border-border rounded-xl p-6 lg:p-8"
                    >
                      <h4 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-primary" />
                        Pipeline Orchestration
                      </h4>
                      <pre className="overflow-x-auto rounded-lg bg-neutral-950 dark:bg-neutral-900 p-4 text-xs sm:text-sm"><code className="font-mono text-neutral-100 dark:text-neutral-50">{`class RAGPipeline:
    def __init__(self, settings: Settings):
        self.vector_store = QdrantVectorStore(settings)
        self.sparse_store = BM25Store(settings)
        self.fusion = RRFusion(settings.rrf_k)
        self.reranker = LLMReranker(settings)
        self.generator = GroundedGenerator(settings)
        self.citations = CitationVerifier(settings)

    async def ask(self, question: str) -> Answer:
        dense_hits = await self.vector_store.search(question)
        sparse_hits = await self.sparse_store.search(question)
        fused = self.fusion.combine(dense_hits, sparse_hits)
        reranked = await self.reranker.score(fused)
        answer = await self.generator.generate(question, reranked)
        verified = await self.citations.verify(answer)
        return verified`}</code></pre>
                    </motion.div>
                  </div>
                </div>
              </div>

              {stageIndex < stages.length - 1 && (
                <div className="hidden lg:block absolute left-1/2 top-full bottom-[-24px] w-0.5 bg-gradient-to-b from-primary/20 via-primary to-primary/20 -translate-x-1/2" />
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}