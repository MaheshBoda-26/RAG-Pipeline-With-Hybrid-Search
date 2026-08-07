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

export function Footer() {
  return (
    <footer className="bg-surface border-t border-border" role="contentinfo">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 lg:py-20">
        <div className="grid lg:grid-cols-[1fr_repeat(3,auto)] gap-8 lg:gap-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            className="lg:col-span-1 max-w-xs"
          >
            <a href="#" className="flex items-center gap-2 text-xl font-semibold text-foreground mb-4" aria-label="RAG Pipeline Home">
              <svg className="w-8 h-8 text-primary" viewBox="0 0 32 32" fill="none" aria-hidden="true">
                <rect x="2" y="2" width="28" height="28" rx="6" className="logo-bg" stroke="currentColor" strokeWidth="2" />
                <path d="M8 12h16M8 16h12M8 20h8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="logo-lines" />
                <circle cx="24" cy="20" r="3" fill="currentColor" className="logo-dot" />
              </svg>
              <span>RAG Pipeline</span>
            </a>
            <p className="text-muted-foreground text-sm leading-relaxed mb-6">
              Production-grade retrieval-augmented generation with hybrid search, LLM reranking, and verified citations.
            </p>
            <div className="flex items-center gap-4">
              <motion.a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
                whileHover={{ scale: 1.1 }}
                aria-label="GitHub"
              >
                <Github className="w-5 h-5" />
              </motion.a>
              <motion.a
                href="#"
                className="text-muted-foreground hover:text-foreground transition-colors"
                whileHover={{ scale: 1.1 }}
              >
                Issues
              </motion.a>
              <motion.a
                href="#"
                className="text-muted-foreground hover:text-foreground transition-colors"
                whileHover={{ scale: 1.1 }}
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
              <h4 className="font-semibold mb-4">{title}</h4>
              <ul className="space-y-3" role="list">
                {links.map((link, i) => (
                  <li key={link.label}>
                    <motion.a
                      href={link.href}
                      className="text-sm text-muted-foreground hover:text-foreground transition-colors"
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
            <h4 className="font-semibold mb-4">Stay Updated</h4>
            <p className="text-sm text-muted-foreground mb-4">
              Get notified about new releases, features, and improvements.
            </p>
            <form className="flex gap-2">
              <input
                type="email"
                placeholder="Enter your email"
                className="flex-1 px-3 py-2 bg-muted/30 border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                aria-label="Email address"
              />
              <Button size="sm" variant="default">
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
          className="mt-12 lg:mt-16 pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4"
        >
          <p className="text-sm text-muted-foreground">
            Built with FastAPI, Qdrant, OpenAI, Next.js, and Framer Motion
          </p>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-primary" />
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