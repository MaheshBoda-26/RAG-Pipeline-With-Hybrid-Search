"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Copy, Check, AlertCircle, Info, Sparkles, Upload, AlertTriangle, RefreshCw, Trash2, FileText } from "lucide-react";

interface DemoDocument {
  source: string;
  chunk_count: number;
  total_chars: number;
}

/** Files bundled with the repo — sample corpus is protected from deletion. */
const SAMPLE_DOC_NAMES = new Set([
  "readme.md", "computer_vision.txt", "data_science.txt", "rag_basics.md", "ml_fundamentals.txt",
]);
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { DocumentUploader } from "@/components/DocumentUploader";
import { PipelineConsole, type PipelineTrace } from "@/components/pipeline-console";
import { ConfidenceDial, CitedAnswer } from "@/components/confidence-dial";

const sampleQuestions = [
  "How do I authenticate with the API?",
  "What happens when I hit the rate limit?",
  "How do I deploy on Kubernetes?",
  "What are the common error codes?",
  "How does the hybrid search work?",
  "What chunking strategies are available?",
];

interface AskResponse {
  answer: string;
  confidence: number;
  sources: Array<{
    id: string;
    source: string;
    text: string;
    score: number;
  }>;
  retrieval: {
    dense: number;
    sparse: number;
    fused: number;
    reranked: number;
  };
  refused?: boolean;
  refusal_reason?: string;
}

export function Demo() {
  const [query, setQuery] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [response, setResponse] = React.useState<AskResponse | null>(null);
  const [trace, setTrace] = React.useState<PipelineTrace | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [config, setConfig] = React.useState({ denseWeight: 0.7, sparseWeight: 0.3 });
  const [ingestState, setIngestState] = React.useState<"idle" | "ingesting" | "done" | "failed">("idle");
  const [ingestMsg, setIngestMsg] = React.useState<string | null>(null);
  const [documents, setDocuments] = React.useState<DemoDocument[]>([]);
  const [deletingSource, setDeletingSource] = React.useState<string | null>(null);

  const refreshDocuments = React.useCallback(async () => {
    try {
      const res = await fetch("/api/demo/documents", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch {
      /* panel is secondary; leave the list as-is on failure */
    }
  }, []);

  React.useEffect(() => {
    refreshDocuments();
    const handler = () => refreshDocuments();
    window.addEventListener("rag:documents-changed", handler);
    return () => window.removeEventListener("rag:documents-changed", handler);
  }, [refreshDocuments]);

  const handleDeleteDocument = async (source: string) => {
    if (deletingSource) return;
    setDeletingSource(source);
    try {
      const res = await fetch(`/api/demo/documents?source=${encodeURIComponent(source)}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Delete failed");
      setDocuments(prev => prev.filter(d => d.source !== source));
      window.dispatchEvent(new Event("rag:documents-changed"));
    } catch (err) {
      setIngestState("failed");
      setIngestMsg(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingSource(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    setResponse(null);
    setTrace(null);
    setError(null);

    try {
      // One backend call returns BOTH the answer and the execution trace
      // (timings, lanes, confidence) — the console below renders the real
      // pipeline run, not a simulation.
      const res = await fetch("/api/demo/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query.trim(), ...weights() }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || data.detail || "Query failed");
      }

      setTrace(data);

      // Transform API response to match expected format
      setResponse({
        answer: data.answer,
        confidence: data.confidence?.composite ?? 0,
        sources: (data.sources || []).map((s: any, i: number) => ({
          id: s.block ? `block-${s.block}` : `source-${i}`,
          source: s.source,
          text: s.text || s.payload?.text || "",
          score: s.rerank_score || s.fused_score || 0,
        })),
        retrieval: {
          dense: 0,
          sparse: 0,
          fused: data.sources?.length || 0,
          reranked: data.sources?.length || 0,
        },
        refused: data.refused,
        refusal_reason: data.refusal_reason,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
      setResponse(null);
      setTrace(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSampleClick = (q: string) => {
    setQuery(q);
  };

  // Per-query fusion weights: sent with every ask so the sliders actually
  // change retrieval behavior (the backend normalizes the pair).
  const weights = () => ({
    dense_weight: config.denseWeight,
    sparse_weight: config.sparseWeight,
  });

  // Seed the demo collection with the bundled corpus. Idempotent upstream
  // (incremental ingest skips unchanged docs), so repeat clicks are safe.
  const handleIngestSample = async () => {
    if (ingestState === "ingesting") return;
    setIngestState("ingesting");
    setIngestMsg(null);
    try {
      const res = await fetch("/api/demo/ingest", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Ingest failed");
      setIngestState("done");
      setIngestMsg(
        data.chunks_indexed > 0
          ? `Indexed ${data.chunks_indexed} new chunks (${data.documents_unchanged} docs unchanged).`
          : `Corpus already indexed (${data.documents_unchanged} docs unchanged).`
      );
    } catch (err) {
      setIngestState("failed");
      setIngestMsg(err instanceof Error ? err.message : "Ingest failed");
    }
  };

  const copyToClipboard = (text: string) => {
    // Clipboard API can reject (unfocused window, iframe permission denial).
    // Fall back to a hidden textarea + execCommand so the button always works.
    const fallback = () => {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(ta);
      }
    };
    navigator.clipboard.writeText(text).catch(fallback);
  };

  return (
    <section
      id="demo"
      className="py-24 sm:py-32 lg:py-40"
      aria-labelledby="demo-title"
      style={{ backgroundColor: 'var(--color-surface)' }}
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="text-center max-w-3xl mx-auto mb-12 lg:mb-16"
        >
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-4">
            <Sparkles className="w-4 h-4" />
            <span>Interactive</span>
          </span>
          <h2 id="demo-title" className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance mb-6">
            Live Query Demo
          </h2>
          <p className="text-lg sm:text-xl text-muted-foreground text-pretty leading-relaxed">
            Ask questions against the sample documentation. Requests are proxied
            to the live pipeline from this page — no API key needed. Answers are
            grounded, cited and confidence-scored; the console below each answer
            shows the real execution.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-[320px_1fr] gap-8 lg:gap-12">
          <motion.aside
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="space-y-6"
          >
            {/* Document Uploader */}
            <DocumentUploader />

            <div className="bg-surface border border-border rounded-xl p-6" style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--color-foreground)' }}>
                <Info className="w-5 h-5 text-primary" />
                Configuration
              </h3>

              <div className="space-y-4">
                <div>
                  <span className="block text-sm font-medium text-muted-foreground mb-1" style={{ color: 'var(--color-muted-foreground)' }}>
                    API Endpoint
                  </span>
                  <p
                    className="w-full px-3 py-2 rounded-md text-sm font-mono"
                    style={{ backgroundColor: 'var(--color-surface-soft)', borderColor: 'var(--color-border)', border: '1px solid var(--color-border)', color: 'var(--color-muted-foreground)' }}
                  >
                    /api/demo/* — same-origin proxy
                  </p>
                </div>

                <div>
                  <label htmlFor="dense-weight" className="block text-sm font-medium text-muted-foreground mb-1" style={{ color: 'var(--color-muted-foreground)' }}>
                    Dense Weight: {config.denseWeight.toFixed(1)}
                  </label>
                  <input
                    id="dense-weight"
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={config.denseWeight}
                    onChange={(e) => setConfig({ ...config, denseWeight: parseFloat(e.target.value) })}
                    className="w-full h-2 rounded-lg appearance-none"
                    style={{ backgroundColor: 'var(--color-surface-soft)', accentColor: 'var(--color-primary)' }}
                  />
                </div>

                <div>
                  <label htmlFor="sparse-weight" className="block text-sm font-medium text-muted-foreground mb-1" style={{ color: 'var(--color-muted-foreground)' }}>
                    Sparse Weight: {config.sparseWeight.toFixed(1)}
                  </label>
                  <input
                    id="sparse-weight"
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={config.sparseWeight}
                    onChange={(e) => setConfig({ ...config, sparseWeight: parseFloat(e.target.value) })}
                    className="w-full h-2 rounded-lg appearance-none"
                    style={{ backgroundColor: 'var(--color-surface-soft)', accentColor: 'var(--color-accent)' }}
                  />
                </div>

                <Button
                  variant="outline"
                  className="w-full"
                  disabled={isLoading || ingestState === "ingesting"}
                  onClick={handleIngestSample}
                >
                  {ingestState === "ingesting" ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Ingesting…
                    </span>
                  ) : (
                    "Ingest Sample Docs"
                  )}
                </Button>
                {ingestMsg && (
                  <p
                    className="text-xs mt-2 font-mono"
                    style={{ color: ingestState === "failed" ? "var(--color-error)" : "var(--color-accent)" }}
                    role="status"
                  >
                    {ingestMsg}
                  </p>
                )}
              </div>
            </div>

            {/* Corpus — live list of indexed documents with per-document delete.
                Sample corpus files are protected; only user uploads are deletable. */}
            <div className="bg-surface border border-border rounded-xl p-6" style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-foreground)' }}>
                  <FileText className="w-5 h-5 text-primary" />
                  Corpus
                </h3>
                <button
                  onClick={refreshDocuments}
                  aria-label="Refresh document list"
                  className="p-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                  style={{ color: 'var(--color-muted-foreground)' }}
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
              {documents.length === 0 ? (
                <p className="text-sm" style={{ color: 'var(--color-muted-foreground)' }}>
                  No documents indexed yet — upload files or ingest the sample corpus.
                </p>
              ) : (
                <ul className="space-y-1.5 max-h-48 overflow-y-auto" role="list">
                  {documents.map(doc => {
                    const name = doc.source.split("/").pop() || doc.source;
                    const deletable = !SAMPLE_DOC_NAMES.has(name.toLowerCase());
                    return (
                      <li
                        key={doc.source}
                        className="flex items-center gap-2 px-2.5 py-2 rounded-lg border text-sm"
                        style={{ backgroundColor: 'var(--color-surface-soft)', borderColor: 'var(--color-border)' }}
                      >
                        <span className="flex-1 min-w-0 truncate font-mono text-xs" style={{ color: 'var(--color-foreground)' }} title={doc.source}>
                          {name}
                        </span>
                        <span className="flex-shrink-0 text-xs tabular-nums" style={{ color: 'var(--color-muted-foreground)' }}>
                          {doc.chunk_count} ch
                        </span>
                        {deletable && (
                          <button
                            onClick={() => handleDeleteDocument(doc.source)}
                            disabled={deletingSource !== null}
                            aria-label={`Delete ${name}`}
                            className="flex-shrink-0 p-1 rounded-md hover:bg-destructive/10 disabled:opacity-40 transition-colors"
                            style={{ color: "var(--color-error)" }}
                          >
                            {deletingSource === doc.source ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="bg-surface border border-border rounded-xl p-6" style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
              <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--color-foreground)' }}>Sample Questions</h3>
              <ul className="space-y-2" role="list">
                {sampleQuestions.map((q, i) => (
                  <motion.li
                    key={q}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <button
                      onClick={() => handleSampleClick(q)}
                      className="w-full text-left p-3 rounded-lg border transition-all duration-200 text-sm text-foreground hover:text-primary text-wrap"
                      style={{ backgroundColor: 'var(--color-surface-soft)', borderColor: 'var(--color-border)' }}
                    >
                      {q}
                    </button>
                  </motion.li>
                ))}
              </ul>
            </div>
          </motion.aside>

          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="space-y-6"
          >
            <form onSubmit={handleSubmit} className="bg-surface border border-border rounded-xl p-6" style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
              <div className="flex gap-3">
                <label htmlFor="query" className="visually-hidden">
                  Your question
                </label>
                <input
                  id="query"
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask a question about the documentation..."
                  className="flex-1 px-4 py-3 rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  disabled={isLoading}
                  autoComplete="off"
                  style={{ backgroundColor: 'var(--color-surface-soft)', borderColor: 'var(--color-border-strong)', color: 'var(--color-foreground)' }}
                />
                <Button
                  type="submit"
                  size="lg"
                  disabled={isLoading || !query.trim()}
                  className="whitespace-nowrap"
                >
                  <span className="flex items-center gap-2">
                    {isLoading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        <span>Thinking...</span>
                      </>
                    ) : (
                      <>
                        <span>Ask</span>
                        <Sparkles className="w-5 h-5" />
                      </>
                    )}
                  </span>
                </Button>
              </div>
            </form>

            <AnimatePresence mode="wait">
              {isLoading ? (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="bg-surface border border-border rounded-xl p-8 text-center"
                  style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
                >
                  <Loader2 className="w-10 h-10 mx-auto mb-4 text-primary animate-spin" />
                  <p className="text-muted-foreground" style={{ color: 'var(--color-muted-foreground)' }}>Searching vector space...</p>
                  <p className="text-sm text-muted-foreground/70 mt-1" style={{ color: 'var(--color-muted-foreground)' }}>Reranking top candidates with the local cross-encoder</p>
                </motion.div>
              ) : response && !response.refused ? (
                <motion.div
                  key="response"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="bg-surface border border-border rounded-xl overflow-hidden"
                  style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
                >
                  <div className="p-6 border-b border-border" style={{ borderColor: 'var(--color-border)' }}>
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-foreground)' }}>
                        <Sparkles className="w-5 h-5 text-primary" />
                        Grounded Answer
                      </h3>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(response.answer)}
                          className="gap-1"
                        >
                          <Copy className="w-4 h-4" />
                          <span className="hidden sm:inline">Copy</span>
                        </Button>
                      </div>
                    </div>

                    {/* Composite confidence: animated dial + per-component bars */}
                    {trace?.confidence && (
                      <div className="mb-5 rounded-lg border p-4" style={{ borderColor: 'var(--color-hairline)', backgroundColor: 'var(--color-surface-soft)' }}>
                        <ConfidenceDial confidence={trace.confidence} refused={response.refused} />
                      </div>
                    )}

                    {/* Answer text with [N] markers as citation hovercards */}
                    <CitedAnswer answer={response.answer} sources={response.sources} />
                  </div>

                  <div className="p-6 space-y-6">
                    <div>
                      <h4 className="font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--color-foreground)' }}>
                        <Info className="w-4 h-4" />
                        Sources & Citations
                      </h4>
                      <div className="space-y-2">
                        {response.sources.map((source, i) => (
                          <motion.div
                            key={source.id}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.05 }}
                            className="p-3 rounded-lg border"
                            style={{ backgroundColor: 'var(--color-surface-soft)', borderColor: 'var(--color-border)' }}
                          >
                            <div className="flex items-start gap-3">
                              <span className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono" style={{ backgroundColor: 'color-mix(in srgb, var(--color-accent) 20%, transparent)', color: 'var(--color-accent)' }}>
                                {i + 1}
                              </span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 text-sm">
                                  <code className="font-mono px-1.5 py-0.5 rounded" style={{ backgroundColor: 'var(--color-surface-soft)', color: 'var(--color-foreground)' }}>{source.source}</code>
                                  <span className="text-muted-foreground" style={{ color: 'var(--color-muted-foreground)' }}>Score: {Math.round(source.score * 100)}%</span>
                                </div>
                                <p className="text-sm text-muted-foreground mt-1 line-clamp-2 font-mono" style={{ color: 'var(--color-muted-foreground)' }}>
                                  {source.text}
                                </p>
                              </div>
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : response?.refused ? (
                <motion.div
                  key="refused"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="bg-warning/10 border border-warning/30 rounded-xl p-6"
                >
                  <div className="text-center">
                    <AlertTriangle className="w-8 h-8 mx-auto mb-3 text-warning" />
                    <h3 className="text-lg font-semibold text-warning mb-2">Could not find enough information</h3>
                    <p className="text-muted-foreground">{response.answer}</p>
                    {response.refusal_reason && (
                      <p className="text-sm text-muted-foreground mt-2 font-mono">{response.refusal_reason}</p>
                    )}
                  </div>
                  {/* Even a refusal shows its real trace — "say so, don't cite" is a designed outcome */}
                  {trace && (
                    <div className="mt-5">
                      <PipelineConsole trace={trace} />
                    </div>
                  )}
                </motion.div>
              ) : error ? (
                <motion.div
                  key="error"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="bg-destructive/10 border border-destructive/30 rounded-xl p-6 text-center"
                >
                  <AlertCircle className="w-8 h-8 mx-auto mb-3 text-destructive" />
                  <h3 className="text-lg font-semibold text-destructive mb-2">Query Failed</h3>
                  <p className="text-muted-foreground">{error}</p>
                  <Button variant="outline" size="sm" onClick={() => setError(null)} className="mt-4">
                    Dismiss
                  </Button>
                </motion.div>
              ) : (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="bg-surface border border-border rounded-xl p-12 text-center"
                  style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
                >
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--color-surface-soft)' }}>
                    <Info className="w-8 h-8 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-foreground)' }}>Ready to query</h3>
                  <p className="text-muted-foreground" style={{ color: 'var(--color-muted-foreground)' }}>Enter a question above or click a sample to see the grounded answer with citations</p>
                </motion.div>
              )}
          </AnimatePresence>

          {/* The real pipeline, exposed: stage timings, lanes, confidence */}
          {trace && !response?.refused && (
            <PipelineConsole trace={trace} />
          )}
          </motion.div>
        </div>
      </div>
    </section>
  );
}