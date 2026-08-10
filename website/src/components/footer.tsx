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
    <footer className="bg-surface-dark text-on-dark-soft" role="contentinfo">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 lg:py-20">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8 lg:gap-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            className="sm:col-span-2 lg:col-span-2 max-w-xs"
          >
            <a href="#" className="flex items-center gap-2 text-lg text-on-dark font-medium mb-4" aria-label="RAG Pipeline Home">
              <SpikeMark />
              <span className="tracking-tight">RAG Pipeline</span>
            </a>
            <p className="text-sm leading-relaxed mb-6">
              Production-grade retrieval-augmented generation with hybrid search,
              LLM reranking, and verified citations. No vendor lock-in — runs on
              your infrastructure.
            </p>
            <div className="flex items-center gap-4">
              <motion.a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-on-dark transition-colors"
                whileHover={{ scale: 1.1 }}
                aria-label="GitHub"
              >
                <Github className="w-5 h-5" />
              </motion.a>
              <motion.a
                href="#"
                className="hover:text-on-dark transition-colors"
              >
                Issues
              </motion.a>
              <motion.a
                href="#"
                className="hover:text-on-dark transition-colors"
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
              <h4 className="text-on-dark font-medium mb-4">{title}</h4>
              <ul className="space-y-3" role="list">
                {links.map((link) => (
                  <li key={link.label}>
                    <motion.a
                      href={link.href}
                      className="text-sm hover:text-on-dark transition-colors"
                      whileHover={{ x: 4 }}
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
            <h4 className="text-on-dark font-medium mb-4">Stay Updated</h4>
            <p className="text-sm mb-4">
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
                className="flex-1 px-3 py-2 bg-surface-dark-elevated border border-white/10 rounded-lg text-sm text-on-dark placeholder:text-on-dark-soft focus:outline-none focus:ring-2 focus:ring-coral"
                aria-label="Email address"
                suppressHydrationWarning
              />
              <Button
                type="submit"
                size="sm"
                className="bg-coral text-on-primary hover:bg-coral-active"
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
          className="mt-12 lg:mt-16 pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4"
        >
          <p className="text-sm">
            Built with FastAPI, Qdrant, OpenAI, Next.js, and Framer Motion
          </p>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-accent-teal" />
              <span>v2.0</span>
            </span>
            <span className="hidden sm:inline">·</span>
            <span>MIT License</span>
          </div>
        </motion.div>
      </div>
    </footer>
  );
}