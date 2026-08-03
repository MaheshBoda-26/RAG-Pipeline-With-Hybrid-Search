# TRD — RAG Pipeline with Hybrid Search Over Internal Docs

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | Uses `X \| None` union syntax and `dataclass` throughout — 3.11+ required, not just 3.10. |
| API framework | FastAPI | `api.py` — thin wrapper over `RAGPipeline`, no business logic in route handlers. |
| Vector database | Qdrant | Embedded/local mode by default (`QdrantClient(path=...)`), no server process. Set `QDRANT_URL` to point at a real Qdrant server instead — same interface either way (`retrieval/vector_store.py`). |
| Sparse index | `rank_bm25` (BM25Okapi), in-memory | Rebuilt from Qdrant's payload data on every ingest — see Data models below for why this is the source of truth. |
| Relational database | None | No document/user/session state is stored outside Qdrant's payload fields. If auth or multi-tenancy is added later, this is the first gap to fill. |
| Hosting | None (local/dev only) | No deployed environment exists yet. See Deployment section. |

## Libraries and packages

| Package | Version (pinned in `requirements.txt`) | Purpose |
|---|---|---|
| `openai` | `>=1.40.0` | Embeddings (`text-embedding-3-small`) and chat completions (`gpt-4o`) for generation, reranking, citation verification, completeness scoring. |
| `qdrant-client` | `>=1.10.0` | Dense vector storage/query. Note: this project's code targets the `query_points()` API (added ~1.10, replaces the deprecated `search()` method removed in later 1.x releases — confirmed against `1.18.0` during build). |
| `rank_bm25` | `>=0.2.2` | BM25Okapi sparse keyword index. |
| `numpy` | `>=1.26.0` | Cosine similarity math (dedup, semantic chunking, RRF is pure Python but candidate vectors use numpy). |
| `pypdf` | `>=4.2.0` | PDF text + per-page extraction. |
| `beautifulsoup4` | `>=4.12.0` | HTML tag stripping (drops `script`/`style`/`nav`/`footer` before extracting text). |
| `python-dotenv` | `>=1.0.0` | Loads `.env` into `os.environ` at `config.py` import time. |
| `fastapi` | `>=0.111.0` | HTTP API layer. |
| `uvicorn[standard]` | `>=0.30.0` | ASGI server to run `api.py`. |
| `pydantic` | `>=2.7.0` | Request/response models in `api.py` (`AskRequest`, `IngestRequest`). |

No LangChain, no sentence-transformers/cross-encoder, no separate
tokenizer library (BM25 uses a regex tokenizer in `retrieval/sparse.py`,
not tiktoken) — deliberate, see `rules.md` for the rationale.

## APIs and third-party integrations

| Integration | Used for | Call sites |
|---|---|---|
| OpenAI Embeddings API (`text-embedding-3-small`, 1536-dim) | Chunk embeddings at ingest, query embedding at ask time | `retrieval/embeddings.py` |
| OpenAI Chat Completions API (`gpt-4o` by default, via `CHAT_MODEL` env var) | (1) LLM-as-judge reranking, (2) grounded answer generation, (3) citation verification, (4) completeness scoring | `retrieval/reranker.py`, `generation/generate.py`, `generation/citations.py` (two functions) |

No other third-party integrations exist. There is no Slack/Confluence/
Google Drive connector for source documents — ingestion is local
filesystem only (`ingestion/loaders.load_directory`).

**Per-query OpenAI call count**: 1 embedding call + up to 4 chat completion
calls (rerank, generate, verify, completeness) — the last three are
skipped only if the retrieval-confidence refusal path fires first.

## Data models and schema

There is no relational schema. The two indexes that exist are kept in sync
by treating **Qdrant as the single source of truth** and rebuilding BM25
from it on every ingest (`RAGPipeline._rebuild_sparse_index`), rather than
maintaining two independently-writable stores.

**`Chunk` (in-memory, `ingestion/chunking.py`)** — the shape every chunking
strategy produces:

| Field | Type | Notes |
|---|---|---|
| `id` | `str` (UUID4) | Used directly as the Qdrant point ID. |
| `text` | `str` | Stripped chunk text. |
| `source` | `str` | Absolute file path of the source document. |
| `chunk_index` | `int` | Position within the source document. |
| `strategy` | `str` | `"fixed" \| "recursive" \| "semantic"` — recorded per-chunk so a corpus ingested under one strategy is distinguishable if you switch strategies later without re-ingesting. |
| `char_count` | `int` | |
| `section_heading` | `str \| None` | Populated by `recursive` strategy only (from markdown headings); always `None` for `fixed`/`semantic`. |
| `embedding` | `list[float] \| None` | Not persisted on the dataclass after upsert — Qdrant is the store of record for vectors. |

**Qdrant point schema** (collection `docs`, configurable via
`Settings.collection_name`):

| Field | Type | Source |
|---|---|---|
| `id` | UUID (string) | `Chunk.id` |
| `vector` | `float[1536]`, cosine distance | OpenAI embedding of `Chunk.text` |
| `payload.text` | string | `Chunk.text` |
| `payload.source` | string | `Chunk.source` |
| `payload.chunk_index` | int | |
| `payload.strategy` | string | |
| `payload.char_count` | int | |
| `payload.section_heading` | string or null | |

**Breaking-change note**: `embedding_dim` (1536) is fixed to
`text-embedding-3-small` in `config.py`. Switching embedding models to one
with a different dimension requires a new collection (or a full
re-ingest) — there's no migration path for changing vector size in place.

## Authentication and authorization

**None implemented.** `api.py` has no auth middleware — every endpoint is
open to any caller who can reach it. This is acceptable for the current
local-only/single-user scope (see PRD Out of scope) but is the first thing
that must change before exposing this beyond localhost:
- No API key / bearer token check on `/v1/ask`, `/v1/ingest`, `/v1/documents`.
- No per-workspace document isolation — `/v1/ingest` writes into the one
  global `docs` collection.
- `/v1/ingest` accepts an arbitrary filesystem `path` with no validation —
  in its current form this is a path-traversal-shaped hole if ever exposed
  to untrusted callers (see `rules.md` boundaries for how this should be
  handled before that happens).

## Performance requirements

No load testing has been done; these are budget targets derived from the
call graph in `pipeline.py:ask()`, not measured production numbers.

| Stage | Expected latency | Why |
|---|---|---|
| Query embedding | ~100–300ms | 1 OpenAI embedding call |
| Dense retrieval (Qdrant) | ~10–50ms | Embedded mode, local disk, small corpus |
| Sparse retrieval (BM25) | <10ms | Pure in-memory Python |
| Fusion (RRF) | <5ms | Pure Python, no I/O |
| Reranking | ~1–3s | 1 batched chat completion over up to 20 candidates |
| Generation | ~2–5s | 1 chat completion, context-length dependent |
| Citation verification | ~1–2s | 1 batched chat completion |
| Completeness scoring | ~1–2s | 1 chat completion |
| **Total `ask()`, p95 target** | **< 10s** | Dominated by the 3 sequential (not parallelized) chat completion calls after retrieval |

**Concurrency**: `uvicorn` runs a single worker by default in this setup.
Embedded Qdrant is single-process (locks its storage directory — see the
"already accessed by another instance" failure encountered and worked
around during testing, `tests/test_pipeline_smoke.py`). **Concurrent
requests are not supported in the embedded-mode configuration** beyond
whatever FastAPI's async request handling gives you for I/O-bound waits on
a single process; true multi-worker concurrency requires switching to
`QDRANT_URL` (a real Qdrant server) first.

**Ingest throughput**: embeddings are batched at 128 texts per OpenAI call
(`retrieval/embeddings.py:BATCH_SIZE`). No batching on the chat-completion
side is relevant to ingest (ingest makes zero chat completion calls unless
`CHUNK_STRATEGY=semantic`, which calls the embedding API per-sentence via
the same batching path).

## Security requirements

- **Secrets**: `OPENAI_API_KEY` is read from `.env` (via `python-dotenv`)
  or the environment; `.env` is gitignored. `config.py:Settings.validate()`
  fails fast with a clear error if the key is missing, rather than letting
  a cryptic 401 surface later.
- **No secrets in payloads or logs**: chunk text and source paths are
  stored in Qdrant payloads in plaintext — do not ingest documents
  containing credentials or secrets, since anything ingested is
  retrievable verbatim by any caller (no auth, see above).
- **Path handling**: `ingestion/loaders.load_directory` walks the given
  path with no sandboxing. `/v1/ingest`'s `path` field is passed straight
  through — treat this as trusted-input-only until auth/validation is
  added.
- **Prompt injection surface**: document content is inserted directly into
  LLM prompts (`generation/prompts.py`, `retrieval/reranker.py`) as context
  blocks. A malicious document could contain text designed to override the
  system prompt's citation rules. Not mitigated currently — out of scope
  for this pass, flagged here as a known gap.
- **Dependency surface**: no dependency pinning to exact versions (only
  lower bounds in `requirements.txt`), so a `pip install` today vs. in six
  months can resolve different versions — this already caused one break
  during development (`qdrant-client`'s `search()` → `query_points()`
  rename between minor versions). Consider pinning exact versions with a
  lockfile before any shared/CI use.

## Deployment and environment setup

| Environment | Status | Setup |
|---|---|---|
| **Dev** | Working | `pip install -r requirements.txt`, `.env` with `OPENAI_API_KEY`, embedded Qdrant at `./qdrant_data` (default), run via `python cli.py` or `uvicorn api:app --reload`. |
| **Staging** | Not built | Would need: a real Qdrant server (`QDRANT_URL` env var — the code path already supports this, untested against a live server), a process manager for `uvicorn` (not just `--reload`), and secrets injected via the platform rather than a `.env` file. |
| **Production** | Not built | All of staging's requirements, plus: authentication (see above), multi-worker `uvicorn` (only viable once off embedded Qdrant), monitoring/logging (currently `print()` statements only — see `rules.md`), and a Dockerfile/compose setup (Phase 6 of `phases.md`, not started). |

## Testing approach

| Type | Status | Where |
|---|---|---|
| **Unit** | Not present as isolated per-function tests. Chunking strategies and the HTML loader were verified with ad-hoc scripts during the build (not checked into the repo as a test suite). | — |
| **Integration (mocked)** | One smoke test covering the full `ingest_directory()` → `ask()` path with the OpenAI client mocked deterministically (`FakeOpenAI` in the test file) — validates dedup-across-ingests, RRF, reranking, citation extraction/verification, confidence scoring, and the low-confidence refusal path, all without real API calls. | `tests/test_pipeline_smoke.py` |
| **Integration (live)** | Not present. No test currently runs against the real OpenAI API or a real Qdrant server. | — |
| **End-to-end (API)** | Not present. No test exercises `api.py`'s HTTP endpoints (e.g. via `TestClient`). | — |
| **Eval suite** (accuracy, not correctness) | Not present — this is Phase 4 of `phases.md`, the golden-Q&A-set evaluation framework. | — |

**Gap to close before calling this production-ready**: real per-module
unit tests (especially the three chunking strategies' edge cases — empty
docs, single-sentence docs, docs with no markdown headings) and at least
one live-API integration test gated behind a secret so CI can run it
without leaking cost on every commit.
