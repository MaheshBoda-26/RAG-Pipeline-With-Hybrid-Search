"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Terminal, Download, Copy, Check, ArrowRight, FileCode, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const steps = [
  {
    number: "1",
    title: "Install Dependencies",
    description: "Install the Python package dependencies and configure your environment.",
    commands: [
      "pip install -r requirements.txt",
      "cp .env.example .env",
      "# Edit .env with your OPENAI_API_KEY",
    ],
    icon: Download,
    color: "primary",
  },
  {
    number: "2",
    title: "Ingest Documents",
    description: "Load your documentation into the vector store using the CLI or REST API.",
    commands: [
      "# CLI",
      "python cli.py ingest ./sample_docs",
      "",
      "# Or via API",
      'curl -X POST localhost:8000/v1/ingest \\',
      '  -H "Authorization: Bearer dev-secret-key" \\',
      '  -H "Content-Type: application/json" \\',
      '  -d \'{"path": "./sample_docs"}\'',
    ],
    icon: FileCode,
    color: "accent",
  },
  {
    number: "3",
    title: "Ask Questions",
    description: "Query the RAG pipeline and get grounded answers with citations.",
    commands: [
      "# CLI",
      'python cli.py ask "How do I authenticate?"',
      "",
      "# Or via API",
      'curl -X POST localhost:8000/v1/ask \\',
      '  -H "Authorization: Bearer dev-secret-key" \\',
      '  -H "Content-Type: application/json" \\',
      '  -d \'{"question": "How do I authenticate?"}\'',
    ],
    icon: Cpu,
    color: "success",
  },
];

const configTable = [
  { variable: "CHUNK_STRATEGY", default: "recursive", description: "fixed | recursive | semantic" },
  { variable: "DENSE_WEIGHT", default: "0.7", description: "Vector search weight" },
  { variable: "SPARSE_WEIGHT", default: "0.3", description: "BM25 search weight" },
  { variable: "RRF_K", default: "60", description: "Reciprocal rank fusion constant" },
  { variable: "RERANK_CANDIDATE_POOL", default: "20", description: "Candidates sent to LLM judge" },
  { variable: "FINAL_TOP_K", default: "5", description: "Final chunks for generation" },
  { variable: "MIN_RETRIEVAL_CONFIDENCE", default: "0.35", description: "Refusal threshold" },
  { variable: "DEDUP_SIMILARITY_THRESHOLD", default: "0.95", description: "Cosine similarity for dedup" },
];

const colorStyles = {
  primary: "bg-primary/10 text-primary border-primary/20",
  accent: "bg-accent/10 text-accent border-accent/20",
  success: "bg-success-500/10 text-success-500 border-success-500/20",
};

export function Docs() {
  const [copied, setCopied] = React.useState<string | null>(null);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(text);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <section
      id="docs"
      className="py-24 sm:py-32 lg:py-40 bg-surface/30"
      aria-labelledby="docs-title"
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
            <span>Get Started</span>
          </span>
          <h2 id="docs-title" className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance mb-6">
            Quickstart
          </h2>
          <p className="text-lg sm:text-xl text-muted-foreground text-pretty leading-relaxed">
            From zero to running RAG pipeline in three commands.
          </p>
        </motion.div>

        <div className="space-y-8 lg:space-y-10">
          {steps.map((step, index) => (
            <motion.article
              key={step.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ delay: index * 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="relative group"
            >
              <div className="grid lg:grid-cols-[80px_1fr] gap-6 lg:gap-8 items-start">
                <div className="lg:order-1 lg:text-right lg:pr-8">
                  <div className="flex items-center justify-end lg:justify-end gap-3 mb-6">
                    <span className="text-4xl font-mono font-bold text-muted-foreground/20">
                      {step.number}
                    </span>
                    <div className="text-right">
                      <div
                        className={cn(
                          "inline-flex items-center justify-center w-14 h-14 rounded-xl mb-3",
                          colorStyles[step.color as keyof typeof colorStyles]
                        )}
                      >
                        <step.icon className="w-7 h-7" aria-hidden="true" />
                      </div>
                      <h3 className="text-2xl font-semibold">{step.title}</h3>
                    </div>
                  </div>
                  <p className="text-muted-foreground leading-relaxed">{step.description}</p>
                </div>

                <div className="lg:order-2 relative">
                  <div className="hidden lg:block absolute left-0 top-14 bottom-0 w-0.5 bg-gradient-to-b from-primary/20 via-primary to-primary/20" />
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true, amount: 0.2 }}
                    transition={{ delay: index * 0.1 + 0.2, duration: 0.4 }}
                    className="relative z-10 bg-neutral-950 dark:bg-neutral-900 rounded-xl overflow-hidden border border-neutral-800"
                  >
                    <div className="flex items-center gap-2 px-4 py-3 border-b border-neutral-800 bg-neutral-900">
                      <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-500" />
                        <div className="w-3 h-3 rounded-full bg-yellow-500" />
                        <div className="w-3 h-3 rounded-full bg-green-500" />
                      </div>
                      <span className="text-xs text-neutral-400 font-mono ml-2">terminal</span>
                    </div>
                    <pre className="p-4 overflow-x-auto"><code className="font-mono text-neutral-100 text-sm leading-relaxed">
{step.commands.map((cmd, i) => (
  <span key={i} className="block">
    {cmd}
    {i < step.commands.length - 1 ? "\n" : ""}
  </span>
))}
                    </pre>
                    <div className="px-4 pb-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCopy(step.commands.join("\n"))}
                        className={cn(
                          "gap-1.5",
                          copied === step.commands.join("\n")
                            ? "text-success-500"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <Copy className="w-4 h-4" />
                        {copied === step.commands.join("\n") ? (
                          <>
                            <Check className="w-4 h-4" />
                            <span>Copied!</span>
                          </>
                        ) : (
                          <span>Copy</span>
                        )}
                      </Button>
                    </div>
                  </motion.div>
                </div>
              </div>
            </motion.article>
          ))}

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ delay: steps.length * 0.1, duration: 0.5 }}
            className="mt-12"
          >
            <div className="bg-surface border border-border rounded-xl overflow-hidden">
              <div className="p-6 border-b border-border">
                <h3 className="text-xl font-semibold flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-primary" />
                  Key Configuration
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-muted/30 border-b border-border">
                      <th className="px-6 py-3 text-left font-semibold text-foreground">Variable</th>
                      <th className="px-6 py-3 text-left font-semibold text-foreground">Default</th>
                      <th className="px-6 py-3 text-left font-semibold text-foreground">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {configTable.map((row, i) => (
                      <tr
                        key={row.variable}
                        className={cn(
                          "border-b border-border/50 hover:bg-muted/30 transition-colors",
                          i === configTable.length - 1 && "border-0"
                        )}
                      >
                        <td className="px-6 py-3 font-mono text-foreground">{row.variable}</td>
                        <td className="px-6 py-3 font-mono text-muted-foreground">{row.default}</td>
                        <td className="px-6 py-3 text-muted-foreground">{row.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}