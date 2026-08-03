# PRD — RAG Pipeline with Hybrid Search Over Internal Docs

## Problem statement

Internal documentation (API references, deployment runbooks, error-code
references, etc.) is written in mixed formats — markdown, plaintext, HTML,
PDF — and scattered across a repo or wiki with no unified search. Two
existing options both fail engineers who need an answer fast:

- **Keyword search** (e.g. a wiki's built-in search) misses questions
  phrased differently than the docs ("how do I log in" vs "authentication
  methods"), and requires the engineer to already know which document to
  open.
- **Unverified LLM summarization** answers fluently but has no mechanism to
  confirm the answer is actually grounded in a real document, so it
  hallucinates confidently on both in-scope and out-of-scope questions —
  which makes it untrustworthy for anything you'd act on (rate limits,
  auth flows, deployment steps).

There is no middle option that combines conversational question-answering
with retrieval that catches both semantic and exact-keyword matches
(function names, config keys, HTTP status codes), and that tells you when
it *doesn't* know rather than guessing.

## What to build

A system that ingests a directory of internal documentation in any
supported format, indexes it with both dense vector and BM25 keyword
search, retrieves and reranks the most relevant passages for a natural-
language question, and generates an answer that cites its sources —
with every citation checked against its source passage after generation,
and a composite confidence score that makes the system refuse to answer
rather than hallucinate when retrieval didn't find enough relevant
material.

## Targeted users

- **Primary: engineers at the org who need answers from internal docs.**
  They ask questions in plain language ("what does error code
  VALIDATION_ERROR mean and is it safe to retry?") and need an answer they
  can trust without re-reading the source doc themselves — which means
  visible citations they can spot-check, not just a confident paragraph.
- **Secondary: whoever evaluates this as a technical/portfolio artifact**
  (a hiring engineer, per the project's stated origin as an interview-
  oriented build). This audience cares about the same things a real
  production user of a RAG system would scrutinize: hybrid retrieval
  quality, chunking strategy trade-offs, and whether citations are
  actually verified rather than decorative.

## Features

### Must-have (built, MVP — Phases 1–3)
- Multi-format ingestion: markdown, plaintext, HTML, PDF, with per-file
  metadata (source path, section heading, PDF page number).
- Three switchable chunking strategies: fixed-size overlap, structure-aware
  recursive (splits on markdown headings), and embedding-similarity
  semantic chunking.
- Near-duplicate detection at ingest time (cosine similarity ≥ 0.95),
  checked against the entire existing index, not just the current batch.
- Hybrid retrieval: dense (Qdrant, cosine similarity) + sparse (BM25),
  combined with Reciprocal Rank Fusion.
- LLM-as-judge reranking of the fused candidate pool before generation.
- Grounded answer generation that must cite context blocks inline.
- Post-generation citation verification: each cited claim is checked
  against its source passage, and unsupported citations are flagged.
- Composite confidence score (retrieval confidence + citation coverage +
  answer completeness) with a refusal path below a configurable threshold.
- CLI (`cli.py`) and a minimal HTTP API (`api.py`) as front ends.

### Nice-to-have (not yet built — Phases 4–6)
- Automated evaluation framework against a golden 50+ question Q&A set,
  scoring answer correctness, faithfulness, retrieval relevance, and
  citation accuracy.
- Chunking-strategy comparison report (same eval suite run once per
  strategy).
- Query dashboard (Streamlit or React) with hybrid-vs-dense-only toggle.
- Docker / docker-compose packaging with a real Qdrant server.
- Authentication/authorization on the API.
- Multi-tenant / multi-workspace document isolation.

## Goals and success metrics

| Goal | Metric | Target |
|---|---|---|
| Answers are grounded, not hallucinated | Citation coverage (Phase 4 eval suite) | ≥ 90% of citing claims verified as supported |
| System knows what it doesn't know | Correct refusal rate on out-of-corpus questions | ≥ 90% |
| Hybrid beats dense-only on this kind of doc set | Retrieval relevance, hybrid vs dense-only (Phase 4 eval) | Hybrid wins on ≥ 60% of questions containing exact identifiers (error codes, config keys, function names) |
| Answers are usable, not just accurate | Answer completeness score | ≥ 0.8 average across eval set |
| Latency is acceptable for interactive use | p95 end-to-end `ask()` latency | < 10s (see TRD Performance for the per-stage budget) |

These targets are provisional until Phase 4 (the eval framework) exists to
actually measure them — right now they're design targets, not measured
results.

## Out of scope

- User authentication, authorization, or per-user access control on
  documents.
- Multi-tenant workspace isolation (one workspace's docs are currently
  fully visible to any caller of the API).
- Non-English document support (chunking regexes and prompts assume
  English; BM25 tokenization is not multilingual-aware).
- Real-time document sync (webhooks from a wiki/Git repo triggering
  re-ingestion). Ingestion is manual/on-demand only.
- Fine-tuning a custom embedding or generation model — this uses
  off-the-shelf OpenAI models only.
- Horizontal scaling / multi-process deployment of the embedded Qdrant
  mode (it locks its storage directory to one process; a real Qdrant
  server is required for that, and is not set up here).
- A production-grade frontend. The dashboard in Phase 5 of the original
  spec is not built.

## Constraints

- **Time**: originally scoped as a 14-day solo build (per the source
  project brief); Phases 1–3 (this MVP) were built in a single session.
- **Budget**: OpenAI API costs only — no other paid infrastructure.
  Every `ask()` call makes at minimum 4 chat-completion calls (rerank,
  generate, verify citations, score completeness) plus 1 embedding call,
  so cost scales with query volume, not just corpus size. No budget cap or
  cost-tracking is implemented yet.
- **Team size**: solo build, no code review process, no dedicated QA.

## Assumptions

- The document corpus is small-to-medium (thousands, not millions, of
  chunks) — embedded Qdrant and an in-memory BM25 index rebuilt on every
  ingest both assume this. A corpus at 10x+ this scale would need a real
  Qdrant server and an incremental BM25 index instead of full rebuild.
- Users have (or the org provides) an OpenAI API key with access to
  `text-embedding-3-small` and `gpt-4o`.
- Questions asked are, in the common case, answerable from the indexed
  corpus. The refusal path handles the exception, but the system is not
  designed as a general-knowledge assistant.
- Documents don't change faster than someone remembers to re-run
  `ingest_directory()` — there's no staleness detection.
