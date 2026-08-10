"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Copy, Check, AlertCircle, Info, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { VectorSpace3D } from "@/components/vector-space-3d";

const sampleQuestions = [
  "How do I authenticate with the API?",
  "What happens when I hit the rate limit?",
  "How do I deploy on Kubernetes?",
  "What are the common error codes?",
  "How does the hybrid search work?",
  "What chunking strategies are available?",
];

const sampleResponse = {
  answer: "To authenticate with the API, include a Bearer token in the Authorization header:\n\n```bash\ncurl -H \"Authorization: Bearer YOUR_TOKEN\" \\\n  http://localhost:8000/v1/ask\n```\n\nThe token must be a valid JWT issued by your authentication provider. Tokens expire after 1 hour and can be refreshed using the `/v1/auth/refresh` endpoint with a valid refresh token.",
  confidence: 0.94,
  sources: [
    { id: "auth-1", source: "authentication.md", text: "API authentication uses Bearer tokens with JWT validation...", score: 0.96 },
    { id: "auth-2", source: "authentication.md", text: "Token refresh endpoint accepts valid refresh tokens...", score: 0.89 },
  ],
  retrieval: { dense: 3, sparse: 2, fused: 5, reranked: 2 },
};

export function Demo() {
  const [query, setQuery] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [response, setResponse] = React.useState<typeof sampleResponse | null>(null);
  const [config, setConfig] = React.useState({ denseWeight: 0.7, sparseWeight: 0.3 });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    setResponse(null);

    await new Promise((resolve) => setTimeout(resolve, 1500));

    setResponse({
      ...sampleResponse,
      answer: sampleResponse.answer.replace("YOUR_TOKEN", "dev-secret-key"),
    });
    setIsLoading(false);
  };

  const handleSampleClick = (q: string) => {
    setQuery(q);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <section
      id="demo"
      className="py-24 sm:py-32 lg:py-40 bg-surface/30"
      aria-labelledby="demo-title"
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
            Ask questions against the sample documentation. The API must be running
            at <code className="bg-muted/30 px-1.5 py-0.5 rounded font-mono text-sm">localhost:8000</code>
            with documents ingested.
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
            <div className="bg-surface border border-border rounded-xl p-6 sticky top-24">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Info className="w-5 h-5 text-primary" />
                Configuration
              </h3>

              <div className="space-y-4">
                <div>
                  <label htmlFor="api-url" className="block text-sm font-medium text-muted-foreground mb-1">
                    API Endpoint
                  </label>
                  <input
                    id="api-url"
                    type="text"
                    value="http://localhost:8000"
                    readOnly
                    className="w-full px-3 py-2 bg-muted/30 border border-border rounded-md text-sm font-mono text-muted-foreground"
                  />
                </div>

                <div>
                  <label htmlFor="dense-weight" className="block text-sm font-medium text-muted-foreground mb-1">
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
                    className="w-full h-2 bg-muted rounded-lg appearance-none accent-primary"
                  />
                </div>

                <div>
                  <label htmlFor="sparse-weight" className="block text-sm font-medium text-muted-foreground mb-1">
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
                    className="w-full h-2 bg-muted rounded-lg appearance-none accent-accent"
                  />
                </div>

                <Button variant="outline" className="w-full" disabled={isLoading}>
                  Ingest Sample Docs
                </Button>
              </div>
            </div>

            <div className="bg-surface border border-border rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">Sample Questions</h3>
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
                      className="w-full text-left p-3 rounded-lg bg-muted/30 hover:bg-muted/50 border border-border transition-all duration-200 text-sm text-foreground hover:text-primary text-wrap"
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
            <form onSubmit={handleSubmit} className="bg-surface border border-border rounded-xl p-6">
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
                  className="flex-1 px-4 py-3 bg-muted/30 border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  disabled={isLoading}
                  autoComplete="off"
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
                >
                  <Loader2 className="w-10 h-10 mx-auto mb-4 text-primary animate-spin" />
                  <p className="text-muted-foreground">Searching vector space...</p>
                  <p className="text-sm text-muted-foreground/70 mt-1">Reranking top candidates with LLM judge</p>
                </motion.div>
              ) : response ? (
                <motion.div
                  key="response"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="bg-surface border border-border rounded-xl overflow-hidden"
                >
                  <div className="p-6 border-b border-border">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold flex items-center gap-2">
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

                    <div className="prose prose-sm dark:prose-invert max-w-none text-foreground">
                      {response.answer.split("\n").map((line, i) => (
                        <p key={i} className="whitespace-pre-wrap font-mono text-sm leading-relaxed">
                          {line}
                        </p>
                      ))}
                    </div>
                  </div>

                  <div className="p-6 space-y-6">
                    <div className="grid sm:grid-cols-3 gap-4">
                      <div className="bg-primary/10 rounded-lg p-4 text-center">
                        <div className="text-3xl font-bold text-primary">{Math.round(response.confidence * 100)}%</div>
                        <div className="text-sm text-muted-foreground">Composite Confidence</div>
                      </div>
                      <div className="bg-accent/10 rounded-lg p-4 text-center">
                        <div className="text-3xl font-bold text-accent">{response.retrieval.reranked}</div>
                        <div className="text-sm text-muted-foreground">Reranked Finalists</div>
                      </div>
                      <div className="bg-success/10 rounded-lg p-4 text-center">
                        <div className="text-3xl font-bold text-success-500">{response.sources.length}</div>
                        <div className="text-sm text-muted-foreground">Verified Citations</div>
                      </div>
                    </div>

                    <div>
                      <h4 className="font-semibold mb-3 flex items-center gap-2">
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
                            className="p-3 bg-muted/30 rounded-lg border border-border"
                          >
                            <div className="flex items-start gap-3">
                              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent/20 text-accent flex items-center justify-center text-xs font-mono">
                                {i + 1}
                              </span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 text-sm">
                                  <code className="font-mono bg-muted px-1.5 py-0.5 rounded">{source.source}</code>
                                  <span className="text-muted-foreground">Score: {Math.round(source.score * 100)}%</span>
                                </div>
                                <p className="text-sm text-muted-foreground mt-1 line-clamp-2 font-mono">
                                  {source.text}
                                </p>
                              </div>
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    </div>

                    <div className="pt-4 border-t border-border">
                      <h4 className="font-semibold mb-3 flex items-center gap-2">
                        <Info className="w-4 h-4" />
                        Retrieval Breakdown
                      </h4>
                      <div className="grid sm:grid-cols-4 gap-3 text-center">
                        <div className="p-3 bg-primary/10 rounded-lg">
                          <div className="text-2xl font-bold text-primary">{response.retrieval.dense}</div>
                          <div className="text-xs text-muted-foreground">Dense Matches</div>
                        </div>
                        <div className="p-3 bg-secondary/10 rounded-lg">
                          <div className="text-2xl font-bold text-secondary">{response.retrieval.sparse}</div>
                          <div className="text-xs text-muted-foreground">Sparse Matches</div>
                        </div>
                        <div className="p-3 bg-accent/10 rounded-lg">
                          <div className="text-2xl font-bold text-accent">{response.retrieval.fused}</div>
                          <div className="text-xs text-muted-foreground">After RRF Fusion</div>
                        </div>
                        <div className="p-3 bg-success/10 rounded-lg">
                          <div className="text-2xl font-bold text-success-500">{response.retrieval.reranked}</div>
                          <div className="text-xs text-muted-foreground">After LLM Rerank</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="bg-surface border border-border rounded-xl p-12 text-center"
                >
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted/30 flex items-center justify-center">
                    <Info className="w-8 h-8 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">Ready to query</h3>
                  <p className="text-muted-foreground">Enter a question above or click a sample to see the grounded answer with citations</p>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </div>
    </section>
  );
}