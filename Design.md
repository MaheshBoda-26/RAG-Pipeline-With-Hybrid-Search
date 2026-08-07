# design.md — RAG Pipeline with Hybrid Search Over Internal Docs

> **Open question carried over from the first pass**: no existing brand
> guidelines, logo, or reference site were provided. This remains an
> assumed from-scratch identity.

**Scope of this pass** (per your answers): a connected site with both a
public landing page and the Phase 5 query dashboard, built around one
real, functional piece — an interactive 3D visualization of the actual
vector space the retrieval system searches, not a decorative animation.
Overall energy stays corporate: the 3D view is a precise instrument,
rendered with restrained motion, not a flashy hero effect.

---

## Library stack

| Library | Version | Role |
|---|---|---|
| **Next.js** | 15.x (App Router) | React framework — needed for both a static-ish landing page and a data-driven dashboard sharing one component library. |
| **Tailwind CSS** | 4.x | Utility CSS, the base every other library here assumes. |
| **shadcn/ui** | latest (CLI-installed, not an npm dependency — components are copied into the repo) | Accessible component primitives (Radix UI underneath) styled with Tailwind. This is what you meant by "shared cn" — its core helper is literally a function called `cn()` (from `clsx` + `tailwind-merge`) used to merge conditional class names; every shadcn component is built on it. |
| **`three`** | 0.169.x | Underlying 3D engine for the vector-space visualization. |
| **`@react-three/fiber`** | 8.x | React renderer for three.js — lets the 3D scene be written as React components/state instead of imperative three.js calls, so it can react to dashboard state (which chunks were retrieved) the same way any other component does. |
| **`@react-three/drei`** | 9.x | Helper primitives on top of fiber: `OrbitControls`, `Line`, `Html` (for node tooltips), `Text`, `Bounds`. Avoids hand-rolling camera controls and label rendering. |
| **`framer-motion`** | 11.x | 2D UI transitions (page/panel/badge animations) — kept separate from the three.js scene, which animates via `useFrame`, not framer-motion, since they're different render loops. |
| **`lucide-react`** | latest | Icon set — shadcn's default, keeps icon style consistent with the components instead of mixing icon libraries. |

**Backend note**: the 3D view needs a 3D projection of each chunk's 1536-
dim embedding, and that reduction (UMAP, not PCA — UMAP preserves local
cluster structure much better, which is the entire point of *looking at*
the space) is too expensive to run client-side or per-request. This
requires a new backend piece not yet in `phases.md`: a precomputed
projection, recalculated once per ingest (not per query) and served via a
new endpoint, e.g. `GET /v1/embeddings/projection` returning
`[{chunk_id, x, y, z, source, strategy}]`. Add `umap-learn` to
`requirements.txt` for this — it's the one new backend dependency this
design pass actually requires.

---

## Color palette

Unchanged from the corporate baseline established earlier — deliberately
not refreshed, per "stay corporate." The 3D view reuses these same tokens
rather than inventing a separate visualization palette, so the graph
never looks like a different product bolted onto the dashboard.

**Primary — "Aegis Blue"**

| Token | Hex | Use |
|---|---|---|
| `primary-50` | `#EEF3FD` | Hover backgrounds, light theme |
| `primary-500` | `#3B6FE0` | Hover state |
| `primary-600` | `#2554C7` | **Base primary** — buttons, links, active nav, dense-retrieval nodes in the 3D view |
| `primary-700` | `#1D42A0` | Pressed state |
| `primary-900` | `#132A66` | High-contrast text-on-light |

**Secondary — Slate**

| Token | Hex | Use |
|---|---|---|
| `secondary-100` | `#E7EAF0` | Secondary button background, light theme |
| `secondary-500` | `#5B6B85` | Muted labels, sparse/BM25-match node outline in the 3D view |
| `secondary-700` | `#33405B` | Secondary button background, dark theme |
| `secondary-900` | `#1B2436` | Header/nav surface, dark theme |

**Accent — Violet** (reserved for verification/confidence signals — same
rule as before, now extended to the 3D view's reranked-finalist nodes,
which is the same underlying concept: "this is what the system trusts
enough to act on")

| Token | Hex | Use |
|---|---|---|
| `accent-100` | `#EDE6FB` | Confidence-badge background, light theme |
| `accent-500` | `#7C3AED` | Confidence bar fill, reranked top-5 nodes in the 3D view, hybrid-toggle active state |
| `accent-700` | `#5B21B6` | Accent text on light backgrounds |

**Semantic** (also reused directly in the 3D view — a citation's
verified/unsupported status uses the exact same colors as the rest of the
UI, not a graph-specific green/red)

| Token | Hex | Use |
|---|---|---|
| `success-500` | `#15803D` | Verified citation ring (both in answer text and on its 3D node) |
| `warning-500` | `#B45309` | Confidence between refusal threshold and 0.8 |
| `error-500` | `#B91C1C` | Unsupported citation flag |
| `info-500` | `#2563EB` | Generic info banners |

**Neutrals**

| Token | Hex | Use |
|---|---|---|
| `neutral-0` | `#FFFFFF` | Light background |
| `neutral-50` | `#F8F9FB` | Light surface |
| `neutral-200` | `#DDE1E7` | Light borders |
| `neutral-400` | `#9AA3B2` | **Unretrieved corpus nodes in the 3D view** — the bulk of chunks on any given query, deliberately the least visually prominent color in the whole system |
| `neutral-600` | `#5B6472` | Secondary text |
| `neutral-800` | `#2A303C` | Dark surface |
| `neutral-950` | `#12151B` | Dark background, and the 3D scene's background/fog color in dark theme |

## Theme rules

- Light and dark, toggle-controlled, persisted client-side (`localStorage`).
- Light theme: background `neutral-0`, surface `neutral-50`, borders
  `neutral-200`, text `neutral-950`/`neutral-600`.
- Dark theme: background `neutral-950`, surface `neutral-800`, borders
  `neutral-600` at 40% opacity, text `neutral-50`/`neutral-400`.
- Primary adapts per theme: `primary-600` on light, `primary-500` on dark
  (contrast against `neutral-950` fails at `-600`).
- **3D scene background**: matches the page background exactly
  (`neutral-0` light / `neutral-950` dark) with a very subtle fog
  (`near: 8, far: 40` in three.js units, fog color = background color) so
  distant nodes fade rather than hard-clipping — this reads as depth, not
  as a decorative gradient.
- WCAG AA minimum (4.5:1 text, 3:1 large text/UI components) — applies to
  the 3D view's node-color legend too: `neutral-400` nodes against
  `neutral-0` background must be checked explicitly, since desaturated
  grays are the most likely token in this palette to fail contrast at
  small node sizes.

## Typography

Unchanged: **Inter** (UI, headings, body), **JetBrains Mono** (source
paths, config keys, error codes, chunk text containing code — and now
also the 3D view's node-hover tooltip, which shows the chunk's source
path and a text preview).

```
--font-sans: "Inter", -apple-system, "Segoe UI", sans-serif;
--font-mono: "JetBrains Mono", "SF Mono", "Consolas", monospace;
```

| Element | Size | Weight | Line height |
|---|---|---|---|
| H1 (landing hero headline) | 40px / 2.5rem | 600 | 1.2 |
| H1 (dashboard page title) | 28px / 1.75rem | 600 | 1.3 |
| H2 (section heading) | 20px / 1.25rem | 600 | 1.35 |
| H3 (card title) | 16px / 1rem | 600 | 1.4 |
| Body (answer text, landing copy) | 15px / 0.9375rem | 400 | 1.6 |
| Body small (chunk previews, metadata) | 13px / 0.8125rem | 400 | 1.5 |
| Label (badges, node-legend labels) | 12px / 0.75rem | 500, uppercase, +0.02em tracking | 1.2 |
| Code / monospace | 13px / 0.8125rem | 400 | 1.5 |

## Spacing and layout scale

4px base unit: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64px`.

- Card padding: 16px (chunk cards), 24px (main answer card).
- Landing page section vertical rhythm: 96px between major sections
  (generous on purpose — corporate sites breathe, they don't cram).
- Dashboard container: 840px max-width for the answer column, 320px side
  panel (confidence + hybrid toggle + docked 3D view) on desktop; the 3D
  view becomes a full-width panel above the answer on mobile rather than
  squeezing into a narrow column where orbit controls become unusable.
- Border radius: 8px cards/inputs, 6px buttons/badges — matches the
  shadcn default radius token (`--radius: 0.5rem`) so custom components
  don't visually clash with shadcn's out-of-the-box ones.

---

## Motion system

Restrained by design — every duration here is short enough that the
motion registers as responsiveness, not performance.

| Token | Duration | Easing | Use |
|---|---|---|---|
| `motion-micro` | 120ms | `ease-out` | Button/badge hover, focus rings |
| `motion-standard` | 200ms | `cubic-bezier(0.4, 0, 0.2, 1)` | Panel open/close, theme toggle crossfade, shadcn `Tabs`/`Switch` state changes |
| `motion-page` | 240ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Landing → dashboard navigation (fade + 8px slide) |
| `motion-emphasis` | 480ms | `cubic-bezier(0.16, 1, 0.3, 1)`, runs once | Confidence bar fill on load (0 → value), never replays on re-render |
| `motion-3d-camera` | 480ms | eased lerp inside `useFrame` (not CSS — three.js camera moves aren't DOM transitions) | Camera refocus when a question is asked and the graph highlights its retrieved subgraph |

**Explicit rule: no spring/bounce/elastic easing anywhere**, including in
`framer-motion` configs — that's the single biggest lever for keeping
this "corporate" rather than "flashy" despite the 3D centerpiece. Nothing
overshoots its target and settles back.

**3D scene motion, specifically**:
- At rest (no query asked): the whole point cloud auto-rotates at
  **2°/second** — barely perceptible, present enough to signal
  "interactive" without drawing focus.
- On `ask()`: unretrieved nodes fade to `neutral-400` at 30% opacity over
  `motion-standard` (200ms); dense-matched nodes brighten to `primary-600`,
  reranked finalists to `accent-500`, over the same 200ms, staggered by
  ~15ms per node in retrieval-rank order (not simultaneous — reads as the
  system "finding" the answer, not repainting instantly) so long as total
  stagger stays under `motion-emphasis`'s 480ms ceiling.
- Camera eases toward centering the highlighted subgraph
  (`motion-3d-camera`, 480ms) — it does not snap, and it does not
  overshoot then correct.
- **`prefers-reduced-motion: reduce`**: disable the idle auto-rotate
  entirely, cut all listed durations to instant (0–50ms), and drop the
  per-node stagger to simultaneous. No exceptions carved out for the 3D
  view — a real accessibility setting doesn't get a "but the graph is
  special" override.

---

## The 3D vector-space visualization

This is the one genuinely novel piece, so it gets its own section rather
than being folded into "component style notes."

**What it shows**: every indexed chunk, positioned in 3D by UMAP-reducing
its 1536-dim OpenAI embedding (see Library stack — precomputed at ingest
time via a new `/v1/embeddings/projection` endpoint, not computed live).
This is the *actual* space `retrieval/vector_store.py` searches — not an
illustration of one.

**Node encoding** (color = retrieval role, reusing the exact palette
tokens above, not a separate graph-only color scheme):

| State | Color | Size |
|---|---|---|
| Not retrieved for this query | `neutral-400`, 30% opacity | small |
| Dense-retrieval match (top-`dense_top_k`) | `primary-600` | medium |
| Sparse/BM25 match (top-`sparse_top_k`) | `secondary-500` outline only (BM25 hits don't have a natural embedding-space proximity to the query, so they're marked distinctly rather than implying they're "close" when they matched on keywords, not geometry) | medium |
| Reranked finalist (final `top_k`, what generation actually used) | `accent-500` | large |
| Citation verified in the answer | `success-500` ring overlay | (adds ring, doesn't change base color/size) |
| Citation flagged unsupported | `error-500` ring overlay | (adds ring) |

**Query node**: rendered distinctly (a small diamond, not a sphere like
chunks) at its own projected position, so it's never confused with an
indexed document.

**Edges**: a thin line (`Line` from drei, `secondary-500` at low opacity)
from the query node to each of the final reranked chunks only — this is
the literal "beam" the answer was built from. No edges between chunks
(would turn into visual noise at any real corpus size) and no edges to
the dense/sparse-only candidates that didn't survive reranking.

**Interaction**:
- `OrbitControls` (drei) for rotate/pan/zoom — standard, no custom camera
  rig, since the goal is inspectability, not a designed camera path.
- Hover a node → `Html` (drei) tooltip: source path (monospace), section
  heading if present, first ~120 characters of chunk text, retrieval role.
- Click a node → scrolls the matching source chunk card into view in the
  dashboard's main panel (and vice versa: hovering a source card
  highlights its node in the 3D view) — the two representations of the
  same data stay linked rather than being two disconnected widgets on the
  same page.
- On the **landing page**, the same component renders in a read-only,
  idle-rotating state showing the full `sample_docs` corpus with no query
  highlighted — a live demonstration of real indexed data, not a canned
  animation, but without the interaction affordances (no orbit controls,
  no tooltips) so it reads as illustrative rather than inviting
  exploration that belongs on the actual dashboard.

---

## Landing page structure

1. **Hero**: headline + one-line problem statement (from `PRD.md`'s
   Problem statement, tightened to a single sentence), the 3D view
   (idle/read-only mode) as the visual anchor beside or behind the copy,
   primary CTA button → dashboard.
2. **Problem section**: 3 cards, `shadcn Card` — keyword search misses
   semantic matches / unverified LLM answers hallucinate / this system
   does neither — each grounded in a specific line from the PRD problem
   statement, not generic RAG marketing copy.
3. **How it works**: horizontal 5-step flow (ingest → hybrid retrieve →
   rerank → generate → verify), mirroring `architecture.md`'s app flow
   exactly — same step names, same order, so the marketing page and the
   technical doc never describe the pipeline differently.
4. **Metrics section**: only populated once Phase 4's eval suite produces
   real numbers. Until then, this section either doesn't render or shows
   an explicit "evaluation in progress" state — never a placeholder number
   that looks real, per the PRD's own discipline about targets vs.
   measured results.
5. **Footer**: repo link, case study link (once written, per `phases.md`
   Phase 6).

## Dashboard structure

- **Main column** (840px max-width): `Textarea` question input +
  `Button`, generated answer with inline citation badges (see below),
  ranked source chunk cards beneath.
- **Side panel** (320px, becomes a `Sheet` drawer on mobile): confidence
  breakdown (3 `Progress` bars + 1 composite), hybrid-vs-dense-only
  `Switch`, and the 3D view docked here in its full interactive mode,
  data-driven by the current question's actual retrieval results.
- **Documents page** (secondary route): list from `GET /v1/documents`,
  an ingest trigger form — lower design priority than the ask flow, can
  use plainer shadcn `Table`/`Form` components without custom treatment.

## Component style notes (shadcn mapping)

| Project element | shadcn component | Notes |
|---|---|---|
| Primary "Ask" action | `Button` (default variant) | `primary-600` fill, 6px radius, no scale-on-press — just the built-in opacity/brightness state change |
| Secondary actions ("Compare hybrid vs. dense") | `Button` (outline variant) | |
| Citation marker in answer text | `Badge`, custom variant | Superscript-positioned, `accent-100`/`accent-700`; add `success-500`/`error-500` ring overlay per verification status — not a stock shadcn variant, needs a small custom variant added to the badge's `cva` config |
| Source chunk card | `Card` | 1px border, no shadow at rest, `hover:shadow-sm` only — signals clickability (links to the 3D node) without looking heavier than the answer card above it |
| Confidence sub-scores | `Progress` | Fill color swapped by value range (`success`/`warning`/`error`) via a wrapper component, not shadcn's default single-color track |
| Hybrid/dense toggle | `Switch` | Active state uses `accent-500`, consistent with "accent = trust/verification-adjacent" rule |
| Node/chunk tooltip (3D view) | `HoverCard` pattern via drei's `Html`, styled to match `Tooltip`'s existing shadcn styling so it doesn't look like a different UI system living inside the canvas |
| Document list | `Table` | |
| Ingest loading state | `Skeleton` | Chunk cards render as skeletons during retrieval latency (see TRD's ~5–10s p95 budget — this is long enough that a spinner alone would feel broken) |