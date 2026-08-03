# RAG Pipeline with Hybrid Search Over Internal Docs

A retrieval-augmented generation system that ingests internal documentation,
indexes it with both dense vector and BM25 sparse search, fuses and reranks
results, and generates grounded answers with verified inline citations and a
composite confidence score.

This covers Phases 1–3 of the full spec (ingestion/chunking, hybrid
retrieval, grounded generation + citation verification) as a working,
runnable system. Phases 4–6 (eval framework, dashboard, Docker packaging)
are not built yet — see "Extending this" below for where they'd plug in.

## Architecture

```
sample_docs/ (.md/.txt/.html/.pdf)
        │
        ▼
  ingestion/loaders.py        multi-format → normalized plaintext + metadata
        │
        ▼
  ingestion/chunking.py       fixed | recursive | semantic (switchable via config)
        │
        ▼
  ingestion/dedup.py          skip near-duplicate chunks (cosine > 0.95)
        │
        ▼
  retrieval/embeddings.py ──► retrieval/vector_store.py (Qdrant, dense)
        │                     retrieval/sparse.py        (BM25, sparse)
        │                             │
        │                             ▼
        │                     retrieval/fusion.py  (Reciprocal Rank Fusion)
        │                             │
        │                             ▼
        │                     retrieval/reranker.py (LLM-as-judge, top-N)
        │                             │
        ▼                             ▼
  generation/prompts.py ──────► generation/generate.py  (grounded answer)
                                        │
                                        ▼
                              generation/citations.py
                              (extract → verify → confidence score)
```

`pipeline.py` wires all of this into two calls: `ingest_directory(path)` and
`ask(question)`. `cli.py` and `api.py` are two thin front ends over the same
`RAGPipeline` class.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in OPENAI_API_KEY
```

Qdrant runs in **embedded mode** by default — a local on-disk folder
(`./qdrant_data`), no separate server process needed. Set `QDRANT_URL` in
`.env` to point at a real Qdrant server instead (needed for concurrent
access — embedded mode locks its storage directory to one process at a
time).

## Usage

```bash
# Ingest the bundled sample docs (a small fictional API's documentation)
python cli.py ingest ./sample_docs

# Ask a question
python cli.py ask "How do I authenticate with the API and what happens if I hit the rate limit?"

# Or run as an API
uvicorn api:app --reload
curl -X POST localhost:8000/v1/ingest -H 'content-type: application/json' -d '{"path": "./sample_docs"}'
curl -X POST localhost:8000/v1/ask -H 'content-type: application/json' -d '{"question": "How do I deploy on Kubernetes?"}'
```

A CLI `ask` call returns something like:

```
A: To authenticate with the API, use either an API key in the Authorization
header [1] or OAuth2 [3]. Exceeding the rate limit returns 429 Too Many
Requests with a Retry-After header [1].

Sources:
  [1] sample_docs/authentication.md (Rate Limits)
  [2] sample_docs/error_codes.md (Common Error Codes)
  [3] sample_docs/authentication.md (OAuth2)
  ...

Confidence:
{
  "retrieval_confidence": 0.87,
  "citation_coverage": 1.0,
  "completeness": 0.9,
  "composite": 0.923
}
```

## Design decisions worth knowing about

- **Chunking is switchable, not fixed.** `CHUNK_STRATEGY` in `.env` picks
  between `fixed` (baseline sliding window), `recursive` (splits on markdown
  headings first, falls back to paragraph/character splitting only when a
  section is too big), and `semantic` (splits on embedding-similarity drift
  between consecutive sentences). Recursive is the default — it's the best
  fit for structured docs (this project's actual use case) without the
  extra embedding calls semantic chunking costs at ingest time.
- **Custom splitters instead of LangChain's.** The spec's tech-stack table
  lists LangChain text splitters; this build implements the three
  strategies directly (~150 lines in `ingestion/chunking.py`) instead of
  pulling in the dependency. Trade-off, not a correction: fewer moving
  parts and the logic is fully inspectable, at the cost of not getting
  LangChain's other splitters for free if you need more later.
- **Dedup is corpus-aware, not just batch-aware.** `DuplicateIndex` is
  seeded from every embedding already in Qdrant before checking a new
  ingest batch, so re-ingesting the same directory (or a directory with
  content that overlaps an earlier one) is fully caught — not just
  duplicates that happen to land in the same `ingest_directory()` call.
- **Reranking is one batched LLM call, not one call per candidate.** All 20
  fused candidates are scored in a single prompt asking for a JSON array of
  relevance scores. Cheaper and faster than N calls; the trade-off is a
  single point of failure per query, handled by falling back to fusion
  order if the model's JSON doesn't parse.
- **Citation verification is also batched**, and only checks claims that
  actually cite something — a sentence with no citation isn't a citation
  accuracy failure, it's a prompt-compliance question (did the model
  correctly say "not covered" instead of citing). Track that separately if
  you build out the eval suite (Phase 4).
- **The confidence score is a composite of three independent signals**:
  retrieval confidence (avg. reranker score, not raw cosine similarity —
  the reranker call is a much better proxy for "did we find the right
  chunk"), citation coverage (fraction of citing claims verified as
  actually supported), and completeness (LLM-judged, did the answer
  address every part of the question given what was available). Below
  `MIN_RETRIEVAL_CONFIDENCE`, the pipeline refuses rather than generating —
  see `pipeline.py:ask()`.

## Testing without an API key

`tests/test_pipeline_smoke.py` runs the full ingest → retrieve → fuse →
rerank → generate → verify pipeline with the OpenAI client mocked out
deterministically (embeddings are keyword-biased pseudo-random vectors;
chat completions are canned responses matched by system-prompt content).
This exercises all the *logic* — fusion math, dedup, the low-confidence
refusal path — without needing a real key or network access:

```bash
python tests/test_pipeline_smoke.py
```

## Extending this to the full spec

- **Phase 4 (eval framework)**: the golden Q&A dataset would live in
  `tests/eval/`, running `RAGPipeline.ask()` against each question and
  scoring with the same `generation/citations.py` primitives
  (`citation_coverage`, `score_completeness`) plus a new answer-correctness
  judge. The chunking-strategy comparison report is just that eval suite
  run three times with `CHUNK_STRATEGY` swapped.
- **Phase 5 (dashboard)**: `api.py` already exposes `/v1/ask`, `/v1/ingest`,
  `/v1/documents` — a Streamlit or React frontend is a thin client over
  those three endpoints. The "hybrid vs dense-only" toggle just means
  calling `ask()` with `sparse_weight=0` for comparison.
- **Phase 6 (Docker)**: `Dockerfile` + `docker-compose.yml` bundling the API
  service and a real Qdrant server (swap `QDRANT_PATH` for `QDRANT_URL` in
  the compose env) — not included here since embedded mode was the chosen
  setup for this pass.
# RAG-Pipeline-With-Hybrid-Search
