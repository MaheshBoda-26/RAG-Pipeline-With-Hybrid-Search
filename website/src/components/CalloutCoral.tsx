"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

/**
 * callout-card-coral — the signature full-bleed coral CTA band.
 * Coral (#cc785c) is the brand voltage, used generously here (the one place
 * where coral may fill a large surface). The internal CTA inverts to a cream
 * button so it reads as the primary action *on* the coral.
 */
export function CalloutCoral() {
  return (
    <section aria-labelledby="callout-title" className="px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl pb-24 sm:pb-28">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="rounded-2xl px-8 py-14 sm:px-14 sm:py-20"
          style={{ backgroundColor: 'var(--color-coral)' }}
        >
          <div className="mx-auto max-w-2xl text-center">
            <h2
              id="callout-title"
              className="text-3xl sm:text-4xl mb-4"
              style={{ color: 'var(--color-on-primary)' }}
            >
              Try it on your own documents
            </h2>
            <p className="text-lg max-w-xl mx-auto mb-8" style={{ color: 'color-mix(in srgb, var(--color-on-primary) 85%, transparent)' }}>
              Ingest, ask, and get a grounded answer with verified citations —
              in three commands.
            </p>
            <a
              href="#docs"
              className="inline-flex items-center gap-2 rounded-lg px-5 py-3 text-sm font-medium transition-colors"
              style={{ backgroundColor: 'var(--color-canvas)', color: 'var(--color-ink)' }}
            >
              View the quickstart
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}