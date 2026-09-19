<div align="center">

<!--
  OPTIONAL UPGRADE — true inline MP4 player:
  GitHub strips <video> tags unless the src is a user-attachments URL, which can only be
  minted by drag-and-drop in GitHub's own UI. To upgrade this animated demo to a real
  player: edit this file on github.com, drag the demo mp4 (local copy:
  brag-output/brag.mp4, or download it from the release link below) into the editor (or
  into any issue's comment box) — GitHub uploads it and prints a
  https://github.com/user-attachments/... URL — then replace the <img> below with:
  <video src="THAT_URL" controls muted playsinline width="100%"></video>
-->

<a href="https://github.com/MaheshBoda-26/RAG-Pipeline-With-Hybrid-Search/releases/download/demo-video/brag-demo.mp4">
  <img src="docs/assets/brag-demo.gif" alt="20-second demo: ingest → hybrid retrieval → rerank → grounded, cited answer" width="100%">
</a>

**A retrieval-augmented generation pipeline that refuses to guess.**

[![CI](https://github.com/MaheshBoda-26/RAG-Pipeline-With-Hybrid-Search/actions/workflows/ci.yml/badge.svg)](https://github.com/MaheshBoda-26/RAG-Pipeline-With-Hybrid-Search/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Lint: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

[Benchmark](#benchmark) · [How it works](#how-it-works) · [Design decisions](#design-decisions-worth-knowing-about) · [Quickstart](#quickstart) · [Evaluation](#evaluation) · [What this is not](#what-this-is-not)

<sub>▶ <a href="https://github.com/MaheshBoda-26/RAG-Pipeline-With-Hybrid-Search/releases/download/demo-video/brag-demo.mp4"><b>Watch the full 20-second demo with sound (MP4)</b></a> · Poster: <a href="docs/assets/brag-poster.jpg">brag-poster.jpg</a></sub>

</div>

# RAG Pipeline with Hybrid Search Over Internal Docs

A retrieval-augmented generation system that ingests internal documentation,
indexes it with both dense vector and BM25 sparse search, fuses and reranks the
results, and generates grounded answers with verified inline citations and a
composite confidence score — refusing to answer when retrieval is weak.

Everything is measured. The numbers below are produced by the harness in
`tests/eval/` over a 54-question golden set, and CI runs the same suite.

## Benchmark

54 questions · `meta/llama-3.1-70b-instruct` judge · local `BAAI/bge-base-en-v1.5`
embeddings · reproducible with `make eval`.

| Metric | Value |
| --- | --- |
| Questions | 54 |
| Answered | 54 |
| Refused | 0 (0.0%) |
| Correctness | 0.854 |
| Faithfulness | 0.981 |
| Citation accuracy | 0.963 |
| Retrieval relevance (judge) | 0.691 |
| **Recall@1** | **0.796** |
| **Recall@3** | **0.944** |
| **Recall@5** | **0.981** |
| **MRR** | **0.873** |
| **NDCG@5** | **0.952** |
| Mean latency | 5.1 s |

Retrieval metrics are **judge-free**: they check whether the chunk containing the
golden passage was retrieved, and at what rank. That separates *retrieval*
failures from *generation* failures — the distinction most RAG projects cannot
measure. Full methodology and raw output: [`docs/benchmarks.md`](docs/benchmarks.md).

The refusal path is not exercised by this golden set (every question is
answerable), so it is covered by unit tests and the confidence-gate tests
instead: `pytest tests/test_pipeline_smoke.py -k refusal`.

## How it works

```mermaid
flowchart LR
    A[docs: md/txt/html/pdf] --> B[loaders<br/>normalise + metadata]
    B --> C[chunking<br/>fixed | recursive | semantic]
    C --> D[cosine dedup<br/>0.95 threshold]
    D --> E[dense: Qdrant HNSW<br/>+ sparse: BM25]
    E --> F[RRF fusion<br/>server-side]
    F --> G[rerank<br/>cross-encoder, LLM fallback]
    G --> H{retrieval<br/>confidence}
    H -- below threshold --> I[refuse + suggest<br/>documents to read]
    H -- ok --> J[generate with<br/>context blocks]
    J --> K[claim extraction +<br/>citation verification]
    K --> L[completeness scoring]
    L --> M[answer + citations +<br/>composite confidence]
```

| Stage | Implementation | Default |
| --- | --- | --- |
| Embeddings | FastEmbed (ONNX) `BAAI/bge-base-en-v1.5`, local, no GPU | 768 dims |
| Dense store | Qdrant (embedded or server) with per-user collections | `./qdrant_data` |
| Sparse | BM25 over the same chunk set | top-10 |
| Fusion | Reciprocal Rank Fusion, k=60 | 0.7 dense / 0.3 sparse |
| Rerank | Cross-encoder `ms-marco-MiniLM-L-6-v2`, LLM fallback | top-15 → top-5 |
| Refusal | Composite confidence gate | min 0.35 |
| Cache | Exact + semantic query cache (Redis, optional) | off |

## Quickstart

```bash
make install                 # runtime + dev dependencies
cp .env.example .env         # add NVIDIA_API_KEY (chat only; embeddings are local)
make demo                    # ingest ./sample_docs, then ask a question
make api                     # FastAPI on :8000, docs at /docs
```

No API key needed just to try retrieval — embeddings run locally, so
`make demo` ingests and answers offline apart from the generation call.

## Design decisions worth knowing about

- **Confidence gating beats confident hallucination.** Retrieval confidence,
  citation coverage and completeness combine into one score; below
  `MIN_RETRIEVAL_CONFIDENCE` the pipeline returns a refusal that names the
  documents worth reading instead of inventing an answer.
- **Claims are verified, not assumed.** Every sentence's `[N]` citations are
  re-checked against the cited passage by a separate model call, and the result
  is published as citation accuracy (0.963 above).
- **Retrieval is measured separately from generation.** Recall@k / MRR / NDCG@5
  come from the golden passages, so a bad answer can always be attributed to
  retrieval or to generation.
- **The golden set ships with its corpus.** `scripts/build_demo_corpus.py`
  generates `sample_docs/aegis/` from the golden contexts and a test asserts
  complete coverage, so the benchmark cannot silently drift.
- **Embedding drift is detected, not ignored.** Chunks record which model
  embedded them; querying a collection built with a different model raises a
  loud warning instead of returning meaningless similarity scores.
- **Deduplication runs against the whole index**, so re-ingesting a corpus is
  idempotent rather than doubling the store.
- **Runs offline by default.** Local embeddings mean the vector space is
  reproducible and free; the LLM is only needed for generation and judging.

## Evaluation

```bash
make eval        # 54-question golden set → tests/eval/results.json
make corpus      # regenerate the demo corpus from the golden set
make check       # lint + types + tests (what CI runs)
```

Metrics computed per run: correctness, faithfulness, citation accuracy and
retrieval relevance (LLM-judged), plus judge-free Recall@1/3/5, MRR and NDCG@5.
The judge-free metrics are unit-tested against known-good values
(`tests/test_eval_metrics.py`) and wired end-to-end in CI by
`tests/test_eval_runner_wiring.py`, which drives the real evaluation loop with
stub clients — so metric regressions fail the build without spending a token.

## Testing

```bash
make test              # self-contained unit suite (no server, no API key)
make test-integration  # security suite against a live API on :8000
```

Tests that need a running server are marked `integration` and skipped unless
`RUN_INTEGRATION_TESTS=1`. The unit suite covers loaders, chunking, reranking
calibration, the refusal path, the API surface with mocked models, the
evaluation metrics, and the corpus/benchmark contract.

## Configuration

All tunables live in [`config.py`](config.py) and are documented in
[`.env.example`](.env.example): chunking strategy, RRF weights, candidate pool,
confidence threshold, cache TTLs, multi-tenancy and upload limits.

## What this is not

- **Not a framework.** No LangChain/LlamaIndex; the pipeline is ~6k lines of
  explicit Python you can read end to end.
- **Not an agent.** There is no tool use or multi-step planning — retrieval,
  reranking and verification only.
- **Not tuned on your corpus.** Defaults are sensible, not optimal; `make eval`
  exists so you can change them with evidence rather than vibes.
- **Not production-hardened for hostile input.** Auth, rate limiting and upload
  validation are real, but the multi-tenant registry is a local JSON file — see
  [`SECURITY.md`](SECURITY.md) for the threat model.

## Roadmap

Shipped: ingestion/chunking/dedup · hybrid retrieval + reranking · grounded
generation with verified citations · evaluation harness · dashboard ·
Docker packaging · CI gates. Next: contextual retrieval, query transformation,
incremental re-indexing and per-stage observability — tracked in
[`docs/TOPTIER_ROADMAP.md`](docs/TOPTIER_ROADMAP.md).

## License

MIT — see [LICENSE](LICENSE).
