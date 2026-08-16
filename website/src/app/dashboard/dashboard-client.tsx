"use client";

import * as React from "react";
import { Search, Sparkles, Zap, CheckCircle, Users, Globe, LogOut, Upload, Settings } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { DocumentUploader } from "@/components/DocumentUploader";

export function DashboardClient() {
  const { user, isLoading, isAuthenticated, mode, setMode, logout, refreshUser } = useAuth();
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
      const endpoint = mode === "demo" ? "/api/demo/ask" : "/api/ask";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
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

  if (isLoading) {
    return (
      <section className="py-24 sm:py-32 lg:py-40 bg-surface/30">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <Zap className="w-5 h-5 animate-spin" />
            <span>Loading...</span>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section id="dashboard" className="py-24 sm:py-32 lg:py-40 bg-surface/30">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Mode Toggle & User Info */}
        <div className="mb-8 animate-in">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium">
                <Sparkles className="w-4 h-4" />
                <span>Live Dashboard</span>
              </span>
              <div className="flex items-center gap-2 border border-border rounded-lg p-1 bg-surface">
                <Button
                  variant={mode === "demo" ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setMode("demo")}
                  className="rounded-md"
                >
                  <Globe className="w-4 h-4 mr-1" />
                  Demo
                </Button>
                <Button
                  variant={mode === "user" ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setMode("user")}
                  className="rounded-md"
                  disabled={!isAuthenticated}
                >
                  <Users className="w-4 h-4 mr-1" />
                  My Documents
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {isAuthenticated && user && (
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-muted-foreground">Logged in as</span>
                  <span className="font-medium">{user.email}</span>
                  <Button variant="ghost" size="sm" onClick={logout} className="gap-1">
                    <LogOut className="w-4 h-4" />
                    Logout
                  </Button>
                </div>
              )}
              {!isAuthenticated && mode === "user" && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>Sign in to use My Documents mode</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Upload Section - Only for authenticated users in user mode */}
        {isAuthenticated && mode === "user" && (
          <div className="mb-8 animate-in">
            <DocumentUploader />
          </div>
        )}

        {/* Demo mode notice */}
        {mode === "demo" && (
          <div className="mb-8 animate-in">
            <div className="bg-primary/5 border border-primary/20 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <Globe className="w-5 h-5 text-primary" />
                <div>
                  <p className="font-medium text-primary">Demo Mode</p>
                  <p className="text-sm text-muted-foreground">
                    Querying pre-loaded demo documents.{" "}
                    {isAuthenticated ? (
                      <span>Switch to &ldquo;My Documents&rdquo; to query your own uploads.</span>
                    ) : (
                      <span>Sign in to upload and query your own documents.</span>
                    )}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="text-center max-w-3xl mx-auto mb-16 animate-in">
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
                    placeholder={mode === "demo"
                      ? "What does the RAG pipeline do? How does hybrid search work? ..."
                      : "What's in my documents? Summarize my uploaded files..."}
                    className="w-full pl-12 pr-4 py-4 bg-surface border border-border rounded-xl text-lg placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    disabled={loading || (mode === "user" && !isAuthenticated)}
                    aria-describedby="query-hint"
                  />
                </div>
                <p id="query-hint" className="mt-2 text-sm text-muted-foreground">
                  {mode === "demo"
                    ? 'Try: "How does reciprocal rank fusion work?" or "What is the chunking strategy?"'
                    : 'Try: "Summarize my documents" or "What are the key topics in my files?"'}
                </p>
              </div>

              <button
                type="submit"
                disabled={loading || !query.trim() || (mode === "user" && !isAuthenticated)}
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
              {(mode === "user" && !isAuthenticated) && (
                <p className="text-sm text-muted-foreground text-center">
                  Please sign in to query your documents
                </p>
              )}
            </form>

            {answer && (
              <div className="bg-surface border border-border rounded-xl p-6 space-y-4 animate-in">
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