"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Github, ArrowRight, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const footerLinks = {
  Resources: [
    { label: "Architecture", href: "#architecture" },
    { label: "Quickstart", href: "#docs" },
    { label: "Live Demo", href: "#demo" },
  ],
  Components: [
    { label: "Hybrid Search", href: "#features" },
    { label: "LLM Reranking", href: "#features" },
    { label: "Verified Citations", href: "#features" },
  ],
  Config: [
    { label: "Chunking Strategies", href: "#docs" },
    { label: "Search Weights", href: "#docs" },
    { label: "Confidence Thresholds", href: "#docs" },
  ],
};

/* Anthropic-style radial-spike brand mark: a 4-spoke asterisk glyph. */
function SpikeMark({ className }: { className?: string }) {
  return (
    <svg
      className={cn("w-6 h-6", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <path d="M12 3v18M4 6l16 12M20 6L4 18" />
    </svg>
  );
}

export function Footer() {
  const [email, setEmail] = React.useState("");

  return (
    <footer className="text-on-dark-soft" role="contentinfo" style={{ backgroundColor: 'var(--color-bg-elev)', borderTop: '1px solid var(--color-border)' }}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 lg:py-20">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8 lg:gap-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            className="sm:col-span-2 lg:col-span-2 max-w-xs"
          >
            <a href="#" className="flex items-center gap-2 text-lg font-medium mb-4" aria-label="RAG Pipeline Home" style={{ color: 'var(--color-text-1)' }}>
              <SpikeMark />
              <span className="tracking-tight">RAG Pipeline</span>
            </a>
            <p className="text-sm leading-relaxed mb-6" style={{ color: 'var(--color-text-2)' }}>
              Production-grade retrieval-augmented generation with hybrid search,
              LLM reranking, and verified citations. No vendor lock-in — runs on
              your infrastructure.
            </p>
            <div className="flex items-center gap-4">
              <motion.a
                href="https://github.com/MaheshBoda-26/RAG-Pipeline-With-Hybrid-Search"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-on-dark transition-colors"
                whileHover={{ scale: 1.1 }}
                aria-label="GitHub"
                style={{ color: 'var(--color-text-2)' }}
              >
                <Github className="w-5 h-5" />
              </motion.a>
              <motion.a
                href="#"
                className="hover:text-on-dark transition-colors"
                style={{ color: 'var(--color-text-2)' }}
              >
                Issues
              </motion.a>
              <motion.a
                href="#"
                className="hover:text-on-dark transition-colors"
                style={{ color: 'var(--color-text-2)' }}
              >
                Changelog
              </motion.a>
            </div>
          </motion.div>

          {Object.entries(footerLinks).map(([title, links], index) => (
            <motion.nav
              key={title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ delay: index * 0.05 + 0.1 }}
              aria-label={`${title} navigation`}
            >
              <h4 className="font-medium mb-4" style={{ color: 'var(--color-text-1)' }}>{title}</h4>
              <ul className="space-y-3" role="list">
                {links.map((link) => (
                  <li key={link.label}>
                    <motion.a
                      href={link.href}
                      className="text-sm transition-colors"
                      whileHover={{ x: 4 }}
                      style={{ color: 'var(--color-text-2)' }}
                    >
                      {link.label}
                    </motion.a>
                  </li>
                ))}
              </ul>
            </motion.nav>
          ))}

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ delay: 0.3 }}
            className="lg:col-span-1"
          >
            <h4 className="font-medium mb-4" style={{ color: 'var(--color-text-1)' }}>Stay Updated</h4>
            <p className="text-sm mb-4" style={{ color: 'var(--color-text-2)' }}>
              Get notified about new releases, features, and improvements.
            </p>
            <form
              className="flex gap-2"
              onSubmit={(e) => e.preventDefault()}
            >
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                className="flex-1 px-3 py-2 rounded-lg text-sm"
                style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border-strong)', color: 'var(--color-text-1)', placeholderColor: 'var(--color-text-3)' }}
                aria-label="Email address"
                suppressHydrationWarning
              />
              <Button
                type="submit"
                size="sm"
                className="hover:bg-coral-active"
                style={{ backgroundColor: 'var(--color-primary)', color: 'var(--color-on-primary)' }}
              >
                <ArrowRight className="w-4 h-4" />
              </Button>
            </form>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.1 }}
          transition={{ delay: 0.4 }}
          className="mt-12 lg:mt-16 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4"
          style={{ borderTop: '1px solid var(--color-border)' }}
        >
          <p className="text-sm" style={{ color: 'var(--color-text-2)' }}>
            Built with FastAPI, Qdrant, OpenAI, Next.js, and Framer Motion
          </p>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5" style={{ color: 'var(--color-text-2)' }}>
              <Sparkles className="w-3.5 h-3.5 text-accent-teal" />
              <span>v2.0</span>
            </span>
            <span className="hidden sm:inline" style={{ color: 'var(--color-text-3)' }}>·</span>
            <span style={{ color: 'var(--color-text-2)' }}>MIT License</span>
          </div>
        </motion.div>
      </div>
    </footer>
  );
}