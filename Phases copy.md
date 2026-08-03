# phases.md — RAG Pipeline with Hybrid Search Over Internal Docs

Status key: ✅ done · 🟡 partial · ⬜ not started

## Phase 1: Ingestion & Chunking Pipeline — ✅ done

**Goal**: turn a directory of mixed-format documents into deduplicated,
embedded chunks in the vector store, with three switchable chunking
strategies to compare later.

**Features/tasks**:
- Multi-format loader: markdown, plaintext, HTML, PDF (`ingestion/loaders.py`)
- Three chunking strategies: fixed, recursive (structure-aware), semantic
  (`ingestion/chunking.py`)
- Corpus-aware near-duplicate detection (`ingestion/dedup.py`)
- Batched embedding generation (`retrieval/embeddings.py`)
- Qdrant upsert + BM25 index rebuild wired into `ingest_directory()`

**Dependencies**: none — this is the foundation phase.

**Definition of done**:
- `python cli.py ingest ./sample_docs` runs against all 3 chunking
  strategies without error.
- Re-ingesting the same directory produces `duplicates_skipped ==
  chunks_created` (verified in `tests/test_pipeline_smoke.py`).
- Every supported file extension has at least one test document exercising it.

---

## Phase 2: Hybrid Retrieval Engine — ✅ done

**Goal**: given a question, retrieve the most relevant chunks using both
semantic and exact-keyword signals, then narrow to a precise top-N.

**Features/tasks**:
- Dense retrieval via Qdrant (`retrieval/vector_store.py`)
- Sparse retrieval via BM25 (`retrieval/sparse.py`)
- Reciprocal Rank Fusion combining both, configurable weights
  (`retrieval/fusion.py`)
- LLM-as-judge reranking of the fused pool, one batched call
  (`retrieval/reranker.py`)

**Dependencies**: Phase 1 (needs an indexed corpus to retrieve against).

**Definition of done**:
- `ask()` returns chunks ranked by `rerank_score`, not raw fusion order.
- Fusion weights (`dense_weight`/`sparse_weight`) are configurable via
  `Settings`, not hardcoded in the fusion function.
- Verified against the mocked smoke test that a question containing both
  a semantic concept and an exact keyword (rate limit / 429) retrieves the
  chunk containing both.

---

## Phase 3: Grounded Generation & Citation Layer — ✅ done

**Goal**: generate an answer that cites its sources, verify those
citations are actually supported, and produce a confidence score that
gates whether to answer at all.

**Features/tasks**:
- Grounded system prompt requiring bracketed citations
  (`generation/prompts.py`)
- Answer generation call (`generation/generate.py`)
- Claim/citation extraction from the generated answer
  (`generation/citations.extract_claims`)
- Batched citation verification against source passages
  (`generation/citations.verify_citations`)
- Completeness scoring (`generation/citations.score_completeness`)
- Composite confidence score + low-confidence refusal path
  (`pipeline.py:ask()`)

**Dependencies**: Phase 2 (needs ranked chunks to generate from and verify against).

**Definition of done**:
- An answer's citations are checked against actual source text, not just
  present syntactically.
- A question with no relevant indexed content triggers the refusal path
  and does not reach the generation call at all (verified in the smoke
  test's forced-low-confidence case).
- `AskResponse.confidence` always contains `retrieval_confidence`,
  `citation_coverage`, `completeness`, and `composite`.

---

## Phase 4: Evaluation Framework — ⬜ not started

**Goal**: replace "these targets feel right" (PRD Goals table) with actual
measured numbers, and produce the chunking-strategy comparison data the
project's stated interview-portfolio goal depends on.

**Features/tasks**:
- Hand-write a 50+ question golden Q&A dataset tied to specific sections
  of `sample_docs/` (or a larger real corpus), including straightforward
  lookups, multi-hop questions, no-answer-in-corpus questions, and
  ambiguous questions.
- Automated eval metrics per test case: answer correctness (LLM-as-judge
  vs. golden answer), faithfulness, retrieval relevance, citation accuracy
  — reusing `generation/citations.py`'s existing primitives
  (`citation_coverage`, `score_completeness`) rather than writing new
  scoring logic from scratch.
- Run the full eval suite once per chunking strategy
  (`fixed`/`recursive`/`semantic`) and produce a comparison report.

**Dependencies**: Phases 1–3 (needs the full pipeline to evaluate).

**Definition of done**:
- A `tests/eval/` (or similar) directory with the golden dataset checked in.
- A single command runs the full suite and outputs per-metric scores plus
  the chunking-strategy comparison table.
- PRD's Goals and success metrics table is updated with actual measured
  numbers, not targets.

---

## Phase 5: API Hardening & Dashboard — 🟡 partial

**Goal**: make the system safe to expose beyond a local trusted process,
and give it a visual front end.

**Features/tasks**:
- ✅ `POST /v1/ask`, `POST /v1/ingest`, `GET /v1/documents` (`api.py`)
- ⬜ Fix eager `RAGPipeline` construction at import time in `api.py` (see
  `rules.md` — this currently means importing the module requires a valid
  API key and an unlocked Qdrant path)
- ⬜ Structured JSON error responses instead of raw tracebacks (`rules.md`
  Error handling rules)
- ⬜ Authentication on all three endpoints (currently fully open — TRD Auth
  section)
- ⬜ Input validation on `/v1/ingest`'s `path` field (currently
  path-traversal-shaped, TRD Security section)
- ⬜ Query dashboard (Streamlit or React): ask a question, see the answer
  with clickable citations, retrieved chunks ranked by relevance,
  confidence breakdown, and a hybrid-vs-dense-only comparison toggle
  (the toggle is just calling `ask()` with `sparse_weight=0`)

**Dependencies**: Phases 1–3 for the API (already met); Phase 4 is not a
hard dependency for hardening but the dashboard's "compare retrieval
modes" view is much more useful once Phase 4's eval numbers exist to
contextualize what a user is looking at.

**Definition of done**:
- API endpoints require authentication and return structured errors.
- `import api` no longer requires a live API key or an unlocked Qdrant
  directory.
- A working dashboard is reachable at a URL, showing at minimum: question
  input, generated answer with citations, source chunks, confidence
  breakdown.

---

## Phase 6: Productionization & Launch Polish — ⬜ not started

**Goal**: package the system for someone else to run with one command, and
package the *portfolio* artifact for its stated purpose (per PRD Targeted
users: a secondary audience evaluating this as an interview project).

**Features/tasks**:
- `Dockerfile` + `docker-compose.yml`: API service + a real Qdrant server
  (swap `QDRANT_PATH` for `QDRANT_URL` in the compose environment — the
  code path already supports this, just untested against a live server)
- A seed script that ingests `sample_docs/` automatically so a reviewer
  can `docker compose up` and query immediately
- Pin exact dependency versions (currently only lower bounds in
  `requirements.txt` — see TRD Security, this already caused one breaking
  change during development)
- Record a demo walkthrough (< 4 minutes): ingesting documents, questions
  of varying difficulty, citation verification catching a hallucination,
  hybrid-vs-dense-only comparison
- Write the case study: lead with the Phase 4 eval numbers (faithfulness
  %, citation accuracy %), explain why hybrid beat dense-only for this
  kind of technical documentation, show the chunking-strategy comparison

**Dependencies**: Phase 4 (the demo and case study both need real
numbers, not targets); Phase 5 (Docker packaging assumes the hardened API
and ideally the dashboard exist to demo).

**Definition of done**:
- `docker compose up` on a clean machine produces a working, queryable
  system with the sample docs pre-indexed.
- The demo video and case study exist and cite actual measured metrics
  from Phase 4, not the provisional targets in the current PRD.
