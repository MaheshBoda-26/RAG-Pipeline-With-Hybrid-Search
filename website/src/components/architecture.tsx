"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  FileText,
  Cpu,
  Search,
  ArrowUpDown,
  Sparkles,
  Activity,
  BarChart2,
} from "lucide-react";

interface PipelineStage {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  details: string[];
  code: string;
}

const PIPELINE_STAGES: PipelineStage[] = [
  {
    id: "ingestion",
    label: "Ingestion",
    description: "Document loading, parsing, and chunking with configurable strategies",
    icon: FileText,
    color: "from-primary-500 to-primary-600",
    details: [
      "Multi-format support (PDF, MD, HTML, DOCX)",
      "Configurable chunking: fixed, recursive, semantic",
      "Metadata extraction & enrichment",
      "Incremental updates with content hashing",
    ],
    code: `def ingest(path: str, strategy: ChunkStrategy = "recursive"):
    docs = load_documents(path)
    chunks = chunk_documents(docs, strategy)
    enriched = enrich_metadata(chunks)
    return vector_store.upsert(enriched)`,
  },
  {
    id: "embedding",
    label: "Embedding",
    description: "Generate dense and sparse vector representations for hybrid search",
    icon: Cpu,
    color: "from-accent-cyan to-accent-teal",
    details: [
      "Dense embeddings (OpenAI, Cohere, local)",
      "Sparse embeddings (BM25, SPLADE)",
      "Batch processing with rate limiting",
      "Cache embeddings for cost efficiency",
    ],
    code: `async def embed(chunks: List[Chunk]) -> EmbeddedChunks:
    dense = await dense_embedder.embed_batch(chunks)
    sparse = sparse_encoder.encode(chunks)
    return EmbeddedChunks(dense=dense, sparse=sparse)`,
  },
  {
    id: "retrieval",
    label: "Retrieval",
    description: "Hybrid vector + keyword search with reciprocal rank fusion",
    icon: Search,
    color: "from-accent-amber to-accent-orange",
    details: [
      "Dense vector similarity (HNSW index)",
      "Sparse lexical search (BM25)",
      "Reciprocal Rank Fusion (RRF)",
      "Configurable dense/sparse weights",
    ],
    code: `def retrieve(query: str, k: int = 20) -> List[Result]:
    dense_results = vector_search(query, k * 2)
    sparse_results = bm25_search(query, k * 2)
    fused = rrf_fuse(dense_results, sparse_results)
    return fused[:k]`,
  },
  {
    id: "reranking",
    label: "Reranking",
    description: "Cross-encoder reranking for precision improvement",
    icon: ArrowUpDown,
    color: "from-accent-pink to-accent-rose",
    details: [
      "Cross-encoder models (Cohere, BGE, local)",
      "Top-k reranking (default: 50 → 10)",
      "Score calibration for thresholding",
      "Async execution for latency hiding",
    ],
    code: `async def rerank(query: str, results: List[Result]) -> List[Result]:
    pairs = [(query, r.text) for r in results]
    scores = await cross_encoder.score(pairs)
    return sorted(zip(results, scores), key=lambda x: x[1], reverse=True)`,
  },
  {
    id: "generation",
    label: "Generation",
    description: "Grounded answer synthesis with citation tracking",
    icon: Sparkles,
    color: "from-success-500 to-success-600",
    details: [
      "RAG prompt templates with context windowing",
      "Streaming responses with citations",
      "Confidence scoring per claim",
      "Hallucination detection heuristics",
    ],
    code: `async def generate(query: str, context: List[Result]) -> Answer:
    prompt = build_rag_prompt(query, context)
    stream = llm.stream(prompt)
    answer = await collect_with_citations(stream)
    confidence = score_confidence(answer, context)
    return Answer(text=answer, confidence=confidence, citations=context)`,
  },
  {
    id: "observability",
    label: "Observability",
    description: "End-to-end tracing, metrics, and real-time monitoring",
    icon: Activity,
    color: "from-purple-500 to-purple-600",
    details: [
      "Distributed tracing (OpenTelemetry)",
      "Latency percentiles per pipeline stage",
      "Token usage & cost tracking",
      "Error rates & alerting thresholds",
      "Live dashboard with drill-down",
    ],
    code: `from opentelemetry import trace

tracer = trace.get_tracer("rag-pipeline")

@tracer.start_as_current_span("rag_query")
async def query_with_tracing(question: str):
    with tracer.start_as_current_span("retrieval") as span:
        results = retrieve(question)
        span.set_attribute("results.count", len(results))

    with tracer.start_as_current_span("generation") as span:
        answer = await generate(question, results)
        span.set_attribute("tokens.used", answer.token_count)

    return answer`,
  },
  {
    id: "evaluation",
    label: "Evaluation",
    description: "Automated quality assessment with golden datasets",
    icon: BarChart2,
    color: "from-indigo-500 to-indigo-600",
    details: [
      "Golden dataset management (Q&A pairs)",
      "RAGAS metrics: faithfulness, answer_relevancy, context_precision",
      "Regression detection on pipeline changes",
      "A/B testing framework for prompt/model variants",
      "CI/CD integration for quality gates",
    ],
    code: `from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

def evaluate_pipeline(dataset: Dataset) -> EvaluationReport:
    results = []
    for sample in dataset:
        answer = pipeline.ask(sample.question)
        results.append({
            "question": sample.question,
            "answer": answer.text,
            "contexts": [c.text for c in answer.citations],
            "ground_truth": sample.expected_answer,
        })

    scores = evaluate(results, metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ])
    return EvaluationReport(scores=scores, passed=all_passed(scores))`,
  },
];

function StageCard({ stage, index }: { stage: PipelineStage; index: number }) {
  const Icon = stage.icon;
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ delay: index * 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="group relative">
        {/* Connection line */}
        {index < PIPELINE_STAGES.length - 1 && (
          <motion.div
            initial={{ scaleY: 0 }}
            whileInView={{ scaleY: 1 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ delay: index * 0.1 + 0.2, duration: 0.4 }}
            className="absolute left-[35px] top-[68px] w-[2px] h-[calc(100%_-_68px)] bg-gradient-to-b from-hairline to-transparent origin-top"
            aria-hidden="true"
          />
        )}

        <div className="flex gap-6 sm:gap-8 relative z-10">
          {/* Left: step indicator + title */}
          <div className="w-[80px] shrink-0 flex flex-col items-center">
            <div className="relative">
              <div className="w-8 h-8 rounded-full border-2 bg-gradient-to-br text-muted flex items-center justify-center font-mono text-xs bg-canvas z-10 relative">
                {String(index + 1).padStart(2, "0")}
              </div>
              <div className="absolute left-1/2 top-8 -translate-x-1/2 w-[2px] h-full bg-hairline/30" />
            </div>
            <h3 className="mt-3 text-ink font-medium tracking-tight text-sm text-center w-[100px]">
              {stage.label}
            </h3>
          </div>

          {/* Right: expandable card */}
          <div className="flex-1 min-w-0">
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: isExpanded ? "auto" : 0, opacity: isExpanded ? 1 : 0 }}
              transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
              className="overflow-hidden"
            >
              <div className="bg-surface-card rounded-xl border border-hairline p-6 space-y-4">
                {/* Description & Details */}
                <div className="space-y-3">
                  <p className="text-muted-foreground text-sm leading-relaxed">
                    {stage.description}
                  </p>
                  <ul className="space-y-2 pl-4">
                    {stage.details.map((detail, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-body">
                        <span className="w-1.5 h-1.5 mt-2 rounded-full bg-coral flex-shrink-0" />
                        <span>{detail}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Code snippet */}
                <div className="bg-surface-dark rounded-lg overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-hairline/10">
                    <span className="w-3 h-3 rounded-full bg-error-500" />
                    <span className="w-3 h-3 rounded-full bg-accent-amber" />
                    <span className="w-3 h-3 rounded-full bg-success-500" />
                    <span className="ml-3 font-mono text-xs text-on-dark-soft">
                      {stage.id}.py
                    </span>
                  </div>
                  <pre className="overflow-x-auto p-4 text-xs sm:text-sm bg-surface-dark-soft">
                    <code className="font-mono text-on-dark">{stage.code}</code>
                  </pre>
                </div>
              </div>
            </motion.div>

            {/* Clickable header */}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="w-full flex items-center gap-4 p-4 bg-surface-card rounded-xl border border-hairline hover:border-hairline/50 transition-all duration-200 text-left focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              aria-expanded={isExpanded}
            >
              <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: stage.color }}>
                <Icon className="w-6 h-6 text-white" aria-hidden="true" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-semibold text-ink">{stage.label}</h3>
                  <motion.span
                    animate={{ rotate: isExpanded ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-muted-foreground"
                  >
                    ▼
                  </motion.span>
                </div>
                <p className="text-sm text-muted-foreground mt-0.5 truncate">
                  {stage.description}
                </p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function Architecture() {
  return (
    <section
      id="architecture"
      className="py-24 sm:py-32 lg:py-40"
      aria-labelledby="arch-title"
    >
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="text-center mb-16 lg:mb-20">
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-coral/10 text-coral text-sm font-medium mb-4">
              <span className="w-1.5 h-1.5 bg-coral rounded-full" />
              <span>System Design</span>
            </span>
            <h2 id="arch-title" className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance text-ink mb-6">
              Architecture Overview
            </h2>
            <p className="text-lg sm:text-xl text-body text-pretty leading-relaxed max-w-3xl mx-auto">
              Modular 7-stage pipeline with clear boundaries. Each stage is independently
              configurable, swappable, and observable — no hard dependencies between stages.
            </p>
          </div>
        </motion.div>

        {/* Pipeline stages */}
        <div className="space-y-6">
          {PIPELINE_STAGES.map((stage, index) => (
            <StageCard key={stage.id} stage={stage} index={index} />
          ))}
        </div>

        {/* Data flow summary */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ delay: 0.7, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mt-16 rounded-2xl bg-gradient-to-r from-primary/5 to-accent/5 border border-hairline p-8"
        >
          <h3 className="text-xl font-semibold text-ink mb-6 text-center">Data Flow</h3>
          <div className="overflow-x-auto">
            <div className="flex items-center gap-3 min-w-max px-4 py-6">
              {PIPELINE_STAGES.map((stage, index) => (
                <React.Fragment key={stage.id}>
                  <div className="flex flex-col items-center gap-2 shrink-0">
                    <div className="w-16 h-16 rounded-xl flex items-center justify-center" style={{ background: stage.color }}>
                      <stage.icon className="w-8 h-8 text-white" aria-hidden="true" />
                    </div>
                    <span className="text-sm font-medium text-ink text-center w-24">{stage.label}</span>
                  </div>
                  {index < PIPELINE_STAGES.length - 1 && (
                    <motion.div
                      initial={{ opacity: 0, scaleX: 0 }}
                      animate={{ opacity: 1, scaleX: 1 }}
                      transition={{ delay: 0.8 + index * 0.1, duration: 0.3 }}
                      className="w-8 h-1 flex-shrink-0"
                    >
                      <svg viewBox="0 0 32 4" fill="none" className="w-full h-full text-hairline">
                        <path d="M0 2H32" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="4 4" />
                        <path d="M28 0L32 2L28 4" stroke="currentColor" strokeWidth="1.5" fill="currentColor" />
                      </svg>
                    </motion.div>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}