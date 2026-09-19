# TOP TIER — The Recruiter-Proof Roadmap

**Project:** RAG Pipeline with Hybrid Search · **Date:** 2026-09-19 · **Verdict first:** the engine is already top-15% of RAG repos on GitHub. What stops it from being top-1% is not capability — it is **trust signals, evaluation evidence, narrative honesty, and visual craft**. This doc is the full plan. No code until you approve.

---

## Part 0 — How a recruiter actually evaluates a repo (research summary)

Synthesized from: 2026 hiring-signal research (AI portfolio teardowns, GitHub community discussions), production-RAG engineering literature (kapa.ai 2026 pipeline guide, RAGAS metric framework, Anthropic contextual-retrieval results), and SaaS design teardowns of Linear / Vercel / Stripe / Cursor / Anthropic / Posthog.

The 30-second scan, in order:

1. **README hero (3s)** — do I understand what this is, and does it look alive?
2. **Proof (10s)** — a demo I can click, a number I can believe (benchmarks), a green CI badge.
3. **Code (10s)** — clean tree, real architecture, no committed secrets, honest claims.
4. **Commits & community (5s)** — LICENSE, meaningful commit history, issues/discussion life.

The killers at each step — and this repo currently dies at step 3:

| Scan step | Top-tier bar | This repo today |
|---|---|---|
| README hero | Working demo + benchmark table + badges | GIF hero ✅, but **no benchmarks, no badges, no LICENSE** |
| Proof | Live demo with **real** numbers, eval results in CI | Demo exists but hardcodes fake sample chunks; evals exist but unpublished, not in CI |
| Code | Clean tree, no secrets | **`.jwt_secret` committed and in remote history** — leaked auth signing key; 235 test-upload debris files tracked; plan-file clutter (`FIX_ALL_ISSUES_PLAN.md` etc.); AI config (`.mcp.json`, `.agents/`) tracked |
| Trust | Claims match code | README/video say "LLM-as-judge reranking"; **code actually uses a cross-encoder** (LLM rerank is only a fallback). README says "eval framework, dashboard, Docker: not built yet" — **all three exist**. The repo undersells AND overclaims at the same time |

Two structural insights from the research:

- **Recruiters hire "evidence of production thinking," not features.** Hybrid search + rerank is table stakes in 2026 — every tutorial has it. Separated retrieval/generation evals, drift detection, refusal paths, semantic caching, security test suites — *these* are rare, and this repo already has all of them. It is sitting on its own moat without claiming it.
- **"The demo is the conversion lift of 2026"** (SaaS teardown pattern #5): interactive in-page demos beat screenshots; interactive widgets that do *one bounded thing* activate visitors in seconds. Your demo section is the single highest-leverage UI investment.

---

## Part 1 — Full audit (what I found, verified)

### 1.1 What is already genuinely strong (protect these, lead with them)

- **Retrieval architecture:** Qdrant native hybrid query (dense + sparse + server-side RRF), cross-encoder rerank with LLM fallback, RRF fusion, configurable chunking (fixed/recursive/semantic), cosine dedup > 0.95.
- **Trust machinery:** retrieval-confidence gate with honest refusals ("say so, don't cite"), claim extraction + citation verification + completeness scoring → composite confidence.
- **Infra sense:** Redis exact + semantic query cache, embedding-model drift detection with loud warnings, multi-tenant collections, per-user upload sandboxing, MIME + magic-byte upload validation, in-memory rate limiting, security headers middleware, SSE streaming endpoint.
- **Test culture:** 58 test files including a dedicated `tests/security/` suite (auth bypass, CORS, rate limiting, file upload, security headers, cookies) — almost nobody does this.
- **Eval scaffold:** golden Q&A set, LLM-judged correctness + faithfulness, mocked mode for deterministic runs.
- **Frontend foundation:** warm editorial palette (cream `#faf9f5`, coral `#cc785c`), Cormorant Garamond display + Inter + JetBrains Mono, framer-motion, a 3D vector-space visualization, `prefers-reduced-motion` already handled.

### 1.2 Critical findings (severity-ordered)

| # | Finding | Severity | Notes |
|---|---|---|---|
| 1 | `.jwt_secret` **tracked in git and present in remote history** (commit `fab3e53e`) | 🔴 Critical | It signs every auth token. Anyone can forge valid sessions for the public demo. Requires rotation + history purge, not just deletion |
| 2 | No CI at all (no `.github/workflows`) despite 58 test files | 🔴 Critical | The single cheapest trust signal you're missing |
| 3 | No LICENSE file | 🔴 Critical | Recruiters and companies read "no license" as "not finished"; also blocks any adoption |
| 4 | 235 files of upload debris tracked in `sample_docs/` (`02361580_doc.txt`, `upload_probe.txt`, …) | 🟠 High | Looks like a test-dump. Curate a real corpus of 5–10 domain docs; ignore the rest |
| 5 | Narrative inconsistency: "LLM-as-judge reranking" (README + brag video) vs actual cross-encoder default | 🟠 High | A code-reading recruiter catches this in one minute. Either ship LLM rerank as a configurable mode or fix every claim |
| 6 | README says Phases 4–6 (evals, dashboard, Docker) "not built yet" — all three exist in the tree | 🟠 High | You are hiding your best work |
| 7 | Repo clutter: `FIX_ALL_ISSUES_PLAN.md`, `SUPABASE_MIGRATION_PLAN.md`, `DEPLOYMENT_NOTES.md`, `file-upload-feature.md`, `.mcp.json`, `.agents/`, stale `website/index.html`+`app.js`+`styles.css` (pre-Next legacy), 4 requirements files | 🟠 High | Exposes raw AI-assisted workflow; signals no curation |
| 8 | Demo site hardcodes fake chunk coordinates (`sampleChunks` in `hero.tsx`) while the real system computes real ones | 🟠 High | The killer feature is 60% built and pointed at fake data |
| 9 | Evals not wired to CI; no recall@k / MRR / NDCG; no published benchmark table | 🟠 High | "Eval framework" exists but produces no evidence anyone can see |
| 10 | `.gitignore` ignores **all** `.md` except README — docs are invisible to the repo (this doc included) | 🟡 Medium | Also why CLAUDE.md and plan files ended up in a weird state |
| 11 | No observability: no structured logs/trace IDs/cost-and-latency per stage | 🟡 Medium | Production story incomplete without it |
| 12 | Auth registry = plaintext JSON (`user_registry.json`) with a self-noted caveat in code | 🟡 Medium | Fine for demo; document the production path (Supabase RLS, already half-built) |
| 13 | No OG/social images, no favicon craft, no architecture diagram in README (there is a generated callflow HTML sitting unused in `graphify-out/`) | 🟡 Medium | Cheap polish wins |
| 14 | `cookies*.txt` in working tree (untracked, gitignored) — fine, but verify before every push | 🟡 Medium | Add a pre-commit guard so they can never be staged |

### 1.3 What the research says the 2026 production bar is (so you build the right things)

- **Contextual retrieval** (Anthropic): prepend 50–100 tokens of chunk situating context before embedding AND before BM25 indexing; hybrid + contextual cut retrieval failure rates ~49–67% depending on setup. It is *the* differentiating ingest upgrade right now.
- **Query transformation**: rewrite/expand/decompose before retrieval — the highest ROI-per-line retrieval upgrade for short user queries.
- **Separate retrieval vs generation evals**: recall@k / MRR / NDCG for retrieval; faithfulness + answer relevancy (RAGAS taxonomy) for generation. End-to-end-only eval is the #1 diagnosable sin.
- **Incremental freshness**: content-hash change detection → re-embed only changed chunks (CDC for unstructured data). Full re-index is the amateur path.
- **Eval-as-gate**: benchmarks run on PR, fail on regression, publish numbers as badges/artifacts. This converts "eval framework" from a folder into a *signal*.
- **Design**: real product UI above the fold (never illustration), bounded interactive demo, performance-as-craft (Lighthouse >90 enforced at component level), dark mode as native for dev tools, honest "what we don't do" sections, numbers-not-adjectives in every claim.

---

## Part 2 — The roadmap

Sequenced so the recruiter-visible delta starts on day 1. Times assume evenings/weekends.

### Phase 0 — Trust & hygiene (do this first; ~3 hours; unblocks everything)

The repo cannot be top-tier while a leaked signing key is in its history. Order matters:

1. **Rotate the secret**: generate a new JWT secret, force the demo to use it. The leaked one is now public knowledge.
2. **Purge history**: `git filter-repo` (or BFG) to remove `.jwt_secret` from all commits, force-push, and invalidate GitHub's cached views. (I will run this only with your explicit approval — it rewrites history and force-pushes.)
3. **Tree curation**: delete/ignore upload debris in `sample_docs/`, remove plan-files + `.mcp.json` + `.agents/` + legacy website static files, collapse 4 requirements files into 1 + lock, `git rm --cached` anything gitignored-but-tracked.
4. **Add LICENSE** (MIT recommended) + `.gitignore` fix: stop ignoring all `.md`; track `docs/`, ignore the rest explicitly.
5. **Pre-commit guards** (the 15-minute kind): block `cookies*.txt`, `.jwt_secret`, `user_registry.json`, large files from ever being staged again.

**Recruiter-visible result:** a repo that survives a 60-second security review — which any senior interviewer *will* run.

### Phase 1 — Evals as the spine (~4–5 days; the core credibility play)

1. **Retrieval metrics**: add recall@k, MRR@k, NDCG@k computed per golden query (labeled relevant chunks already implied by your Q&A set). Split reports: retrieval vs generation, so a bad answer is always attributable.
2. **Generation metrics**: keep LLM-judge correctness + faithfulness; add RAGAS-style answer-relevancy. Deterministic mocked mode stays as the CI path.
3. **Benchmark table in README** — real numbers from a real run, with corpus size, judge model, and date. Numbers-not-adjectives is the whole game ("refuses 41% of unanswerable questions with 0 false citations" beats "high accuracy").
4. **CI gate**: GitHub Actions — pytest (with security suite), ruff, mypy, next build, and a nightly eval run that comments the delta on PRs touching retrieval. Badge row in README: CI · License · Python · eval results.
5. **Sweep artifact**: one chunk-size × strategy × rerank-mode sweep over the golden set, published as a small table/chart in `docs/benchmarks.md`. This single artifact says "engineer who measures" louder than any feature.

**Result:** the repo now *proves* quality instead of claiming it. This is the #1 differentiator vs 95% of RAG repos.

### Phase 2 — Production hardening (~5–8 days; deepens the moat you already have)

1. **Honest reranker story**: cross-encoder as default, LLM-as-judge as a documented config mode (`RERANK_MODE=llm|cross-encoder`), then fix every README/video/site claim to match. (Optionally evaluate a BGE-reranker-v2 for a third data point in the sweep.)
2. **Contextual retrieval**: chunk-situating context prepended before embedding + BM25 indexing (cache the generated contexts to keep ingest cheap). Benchmark before/after on the golden set — if it moves the needle, it becomes the headline feature of v3.
3. **Query transformation**: optional rewrite/expansion step before retrieval, behind a config flag, evaluated on the golden set.
4. **Incremental ingestion**: content-hash per document; re-chunk/re-embed only changed docs; handle deletions. Kills the "full rebuild on every change" smell.
5. **Observability**: structured JSON logs with request trace IDs, per-stage timings (embed → retrieve → fuse → rerank → generate → verify), token counts and $ cost per request. No new vendor needed to start; OpenTelemetry hooks as stretch.
6. **Auth prod-path doc**: keep the JSON registry for dev; document (and wire behind a flag) the Supabase Postgres + RLS path that's already half-built. Add a `SECURITY.md` threat model — this doc is rare and interviewers love it.
7. **Deploy story**: one-command `make demo` (docker-compose up → seeded corpus → site talking to it), plus the live hosted demo URL. A recruiter must go from zero to asking a question in under 60 seconds without an API key.

### Phase 3 — Narrative & docs (~2 days; rewrite the story to match reality)

1. **README restructure**: hero → one-line value prop → live demo link → **benchmark table** → 60-second quickstart → honest architecture diagram (convert the unused `graphify-out` callflow into a clean SVG) → "Design decisions worth knowing" (drift detection, refusal gate, RRF k, cache invalidation) → "What this is not" section (the disqualification pattern — it reads as senior) → roadmap.
2. **Kill the underselling**: eval framework ✅, dashboard ✅, Docker ✅ — update the phase-status table to reflect shipped reality.
3. **`docs/architecture.md`**: the measured-decisions doc — why server-side RRF, why cosine 0.95 dedup, why confidence-gated refusals, what the sweep showed. This is the artifact a Staff engineer reads and says "hired."
4. **`docs/benchmarks.md`** + the eval chart, kept honest by CI.

### Phase 4 — Website UI/UX overhaul (~5–7 days; detailed spec in Part 3)

### Phase 5 — The differentiators (the "no one else has this" tier, ~1–2 weeks, pick 2)

1. **Live Pipeline Console** (the flagship): the website hero runs a real, bounded demo — a fixed set of questions against the public corpus — and shows the *actual* pipeline executing: stage timings, dense vs sparse lanes racing, fusion, rerank reorder with real scores, confidence breakdown. Not a video; the real thing, read-only.
2. **Real 3D vector space**: wire `vector-space-3d.tsx` to genuine chunk coordinates from the demo corpus's actual embeddings (currently hardcoded fake points). One endpoint, cached, read-only. Watching the query point fly in and the retrieval set light up is the moment recruiters remember.
3. **Citation hovercards**: hovering `[1]` in an answer reveals the exact source passage with the cited sentences highlighted — the product's core promise, made tangible.
4. **Confidence dial**: animated arc + per-component bars (retrieval / coverage / completeness) with the refusal state designed as a first-class citizen ("say so, don't cite" as a visual).
5. **Eval chart section**: the CI benchmark numbers rendered as data-viz on the site, auto-updated by CI. Living proof.

### Phase 6 — Distribution (1 day, after the above)

- OG/social card (we already have the poster aesthetic), repo topics + description polish, "About" links, GitHub Discussions enabled, one short technical writeup ("What 235 test uploads taught me about evaluating RAG" — the honest angle gets read), Hacker News / r/Rag launch when the live demo + benchmarks exist.

---

## Part 3 — UI/UX design system spec (decisions, not code)

### 3.1 The anti-slop thesis

AI-slop websites share a DNA: dark navy → purple gradient, Inter everywhere, glassmorphic cards, glow blobs, "AI-powered" headline, emoji section markers. Your current identity — **warm paper, editorial serif, coral ink, terminal mono** — is already the opposite. The plan is not a rebrand; it's *craft elevation*: keep the soul, fix the execution. (Teardown principle: copy the structural decisions, never the surface.)

### 3.2 Typography — the identity carrier

- **Display**: switch Cormorant Garamond → **Fraunces** (variable, optical sizes, subtle "wonk"). Same editorial feeling, dramatically more character at 60–110px. Headlines oversized (`clamp(3rem, 6vw, 6.5rem)`), tight tracking, tight leading — type *is* the design element on the strongest 2026 sites.
- **Body/UI**: Inter stays but demoted to UI-only (buttons, labels, forms). Long prose gets a serif reading face (Newsreader or Source Serif) at `max-w-prose` — instant editorial feel.
- **Mono**: JetBrains Mono is the *third voice* — all scores, numbers, code, stage labels. Use it aggressively as a design element (mono microlabels with letter-spacing + uppercase above every section: `01 · INGEST`).
- Load via `next/font` with `display: swap` and subset — performance is part of the aesthetic.

### 3.3 Color & texture

- Keep: cream canvas `#faf9f5`, ink `#141413`, coral `#cc785c` primary, teal `#5db8a6` + amber `#e8a55a` accents.
- Add: a data-semantic ramp for pipeline stages (ingest = amber, dense = coral, sparse = teal, rerank = deep green) used consistently across console, 3D view, and diagrams.
- Texture instead of gradients: a barely-there paper grain (1–2% opacity noise) on the canvas and a fine dot-grid behind the 3D hero. Zero purple-blue gradients anywhere. Dark sections (footer, AI band, terminal) use your existing `#181715` family with hairline borders — no glassmorphism.

### 3.4 Motion — "reward attention, never demand it" (Linear's law)

- One system: 120–480ms, `cubic-bezier(0.16, 1, 0.3, 1)`, 8–24px travel. Already in your tokens — enforce it everywhere and delete one-off easings.
- Scroll-linked reveals with `whileInView`, staggered 50–80ms, once per page load.
- **The hero is a live pipeline replay**: on load, a query types itself, the two retrieval lanes race in, fusion merges, scores count up in mono, the confidence dial sweeps. ~4s, then rests, loops on scroll re-entry. This replaces passive animation with *product explanation* — the pattern every top-converting dev-tool site converged on.
- Number tickers for every metric; magnetic hover on primary buttons; View Transitions API for page swaps; everything gated behind `prefers-reduced-motion` (already handled — keep it).

### 3.5 The five components that make it feel expensive

1. **Pipeline Console** (Phase 5.1) — real timings, real scores, mono type, stage colors. The product *is* the hero image (teardown pattern #1: real product UI above the fold).
2. **Real vector space** (5.2) — actual embeddings, query fly-in, role-colored points.
3. **Citation hovercards** (5.3) — the trust promise, made interactive.
4. **Confidence dial** (5.4) — refusal designed as first-class.
5. **Benchmark band** (5.5) — CI numbers as data-viz, with a "view run" link to the GitHub Action.

### 3.6 Craft details that read as "expensive"

Custom favicon + OG card; selection color; custom scrollbar on code blocks; hairline dividers instead of card borders where possible; 120–160px section rhythm on an 8px grid; footer as a dark terminal block with the pipeline's actual refusal line as a closing joke (`"I couldn't find enough relevant information…"`); Lighthouse ≥90 enforced in CI (performance-as-craft is a trust signal, not a chore); copy pass to kill every "AI-powered" phrasing in favor of concrete claims.

### 3.7 Anti-slop checklist (before any merge)

☐ No purple/blue gradients ☐ No glass blur cards ☐ No emoji in section headers ☐ No "revolutionary/empower/seamless" ☐ Every number real and sourced from CI ☐ Every claim matches code behavior ☐ Reduced-motion respected ☐ Keyboard + screen-reader pass on all new components ☐ Lighthouse ≥ 90

---

## Part 4 — Priority & effort matrix

| Phase | Effort | Recruiter impact | Notes |
|---|---|---|---|
| 0 Trust & hygiene | ~3h | 🔥🔥🔥 | Blocks everything; do first |
| 1 Evals as spine | 4–5 days | 🔥🔥🔥 | The #1 credibility differentiator |
| 3 Narrative & docs | 2 days | 🔥🔥🔥 | Cheapest high-impact rewrite |
| 4 Website UI/UX | 5–7 days | 🔥🔥 | Spec'd above; demo-first order |
| 2 Hardening | 5–8 days | 🔥🔥 | Contextual retrieval may become the headline |
| 5 Differentiators | 1–2 weeks | 🔥🔥 | Pick 2 — console + real 3D are the pair |
| 6 Distribution | 1 day | 🔥 | Only after live demo + benchmarks exist |

**Total: ~4–6 weeks part-time.** The repo reads as top-tier after Phases 0+1+3 alone (~1 week).

## Part 5 — What NOT to build (the Karpathy clause)

- ❌ GraphRAG / multi-agent orchestration / fine-tuning — scope creep that dilutes a clean story.
- ❌ Kubernetes/helm packaging for a demo — one `make demo` beats a cluster.
- ❌ A second frontend framework, SaaS pricing pages, user-facing accounts — it's a portfolio piece, not a startup.
- ❌ More features before the evals exist — any feature added without a benchmark is un-evidenced work.
- ❌ Rewriting the design from scratch — elevate, don't rebrand.

---

## Sources consulted

- kapa.ai — "How to Build a RAG Pipeline from Scratch in 2026" (production components, contextual retrieval, incremental updates, eval taxonomy)
- RAGAS docs — official metric list (faithfulness, answer relevancy, context precision/recall)
- designkey.studio — 12-pattern teardown of Linear / Vercel / Stripe / Cursor / Anthropic / Posthog / Resend (2026)
- metobole.studio / metabrand — 2026 best-site analyses (typography-as-design, performance-as-craft)
- GitHub community + 2026 AI-portfolio hiring-signal research
- Full local audit of this repository (every claim in Part 1 verified against tracked files and git history)
