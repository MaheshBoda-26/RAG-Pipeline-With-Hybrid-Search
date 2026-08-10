"use client";

import * as React from "react";
import { Search, Sparkles, Zap, CheckCircle } from "lucide-react";

export function DashboardClient() {
  const [query, setQuery] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [answer, setAnswer] = React.useState("");
  const [citations, setCitations] = React.useState<string[]>([]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setAnswer("");
    setCitations([]);

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: query }),
      });

      const data = await res.json();
      setAnswer(data.answer || "No answer returned");
      setCitations(data.citations || []);
    } catch (err) {
      setAnswer("Error: " + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section id="dashboard" className="py-24 sm:py-32 lg:py-40 bg-surface/30">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div
          className="text-center max-w-3xl mx-auto mb-16 animate-in"
        >
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-4">
            <Sparkles className="w-4 h-4" />
            <span>Live Dashboard</span>
          </span>
          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance mb-6">
            Query the Pipeline
          </h2>
          <p className="text-lg sm:text-xl text-muted-foreground text-pretty leading-relaxed">
            Ask questions against your ingested documents. Get grounded answers with verified inline citations.
          </p>
        </div>

        <div className="grid lg:grid-cols-[1fr_350px] gap-8 lg:gap-12">
          <div className="space-y-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="relative">
                <label htmlFor="query" className="sr-only">
                  Your question
                </label>
                <div className="relative">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" aria-hidden="true" />
                  <input
                    id="query"
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="What does the RAG pipeline do? How does hybrid search work? ..."
                    className="w-full pl-12 pr-4 py-4 bg-surface border border-border rounded-xl text-lg placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    disabled={loading}
                    aria-describedby="query-hint"
                  />
                </div>
                <p id="query-hint" className="mt-2 text-sm text-muted-foreground">
                  Try: "How does reciprocal rank fusion work?" or "What is the chunking strategy?"
                </p>
              </div>

              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="w-full sm:w-auto px-8 py-4 bg-primary text-primary-foreground rounded-xl font-medium text-lg hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none transition-all active:scale-[0.98] flex items-center gap-2 justify-center"
              >
                {loading ? (
                  <>
                    <Zap className="w-5 h-5 animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5" />
                    Ask
                  </>
                )}
              </button>
            </form>

            {answer && (
              <div
                className="bg-surface border border-border rounded-xl p-6 space-y-4 animate-in"
              >
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle className="w-4 h-4 text-success-500" />
                  <span>Grounded answer with {citations.length} citation{citations.length !== 1 ? "s" : ""}</span>
                </div>
                <div className="prose prose-neutral dark:prose-invert max-w-none">
                  <p className="whitespace-pre-wrap text-foreground">{answer}</p>
                </div>
                {citations.length > 0 && (
                  <details className="group">
                    <summary className="cursor-pointer flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
                      <span>View citations</span>
                    </summary>
                    <ul className="mt-3 space-y-2 pl-6 list-disc">
                      {citations.map((c, i) => (
                        <li key={i} className="text-sm text-muted-foreground font-mono">{c}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}
          </div>

          <div className="hidden lg:block">
            <div className="bg-surface border border-border rounded-xl p-6 h-full">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-primary" />
                Vector Space
              </h3>
              <div className="aspect-square bg-neutral-950 dark:bg-neutral-900 rounded-lg relative overflow-hidden">
                <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                  <p className="text-center px-4">3D visualization loads here when API connected</p>
                </div>
              </div>
              <ul className="mt-6 space-y-3 text-sm">
                <li className="flex items-center gap-2 text-muted-foreground">
                  <CheckCircle className="w-4 h-4 text-success-500 flex-shrink-0" />
                  UMAP projection of embeddings
                </li>
                <li className="flex items-center gap-2 text-muted-foreground">
                  <CheckCircle className="w-4 h-4 text-success-500 flex-shrink-0" />
                  Query highlighted in real-time
                </li>
                <li className="flex items-center gap-2 text-muted-foreground">
                  <CheckCircle className="w-4 h-4 text-success-500 flex-shrink-0" />
                  Retrieved chunks visualized
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}