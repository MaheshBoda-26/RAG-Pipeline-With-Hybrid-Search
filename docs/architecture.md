# Architecture and measured decisions

This document records *why* the pipeline is built the way it is, with the
numbers that back each choice. Anything below can be re-measured with `make eval`.

## Data flow

```
loaders → chunking → cosine dedup → embeddings → vector store (dense)
                                   ↘ BM25 index (sparse)
ask(): embed query → hybrid query (dense + sparse + RRF) → rerank → confidence gate
      → generate → claim extraction → citation verification → completeness → composite
```

Modules: `ingestion/` (loaders, chunking, dedup), `retrieval/` (embeddings,
vector_store, sparse, fusion, reranker, query_cache, supabase_store),
`generation/` (prompts, generate, citations), `pipeline.py` (orchestration),
`api.py` (HTTP surface), `cli.py`, `dashboard/`, `website/`.

## Decisions

**Local embeddings, not a hosted embedding API.**
Embeddings run through FastEmbed (ONNX, `BAAI/bge-base-en-v1.5`, 768 dims) on
CPU. This makes the vector space reproducible, removes a network dependency from
the retrieval path, costs nothing per query, and removes a whole class of
"dimension drift between providers" bugs. NVIDIA's hosted embedding endpoints
(`nv-embedqa-*`, `bge-m3`) now return 410 Gone, which would have broken the
previous configuration silently — the code falls back to a local model and pins
the process to that backend rather than mixing vector spaces.

**Server-side hybrid search with RRF, k=60.**
Dense (HNSW) and sparse (BM25) candidates are fused with Reciprocal Rank Fusion.
RRF is used instead of score normalisation because it needs no per-corpus
calibration: only ranks matter, so a change in embedding model or corpus size
does not invalidate the weights. `k=60` is the value from the original RRF
paper and is the default most engines ship; the dense/sparse weights (0.7/0.3)
are the knobs worth tuning per corpus.

**Rerank before generating, and never trust fusion scores as relevance.**
The cross-encoder (`ms-marco-MiniLM-L-6-v2`) scores query–passage pairs jointly.
When it is unavailable the pipeline keeps fusion *order* but caps the reported
score at 5.0/10, because a fused rank carries no absolute relevance signal —
uncapped fallback scores would let the pipeline claim confidence it does not
have and bypass the refusal gate.

**Refusal is a feature.**
Retrieval confidence, citation coverage and completeness combine into a
composite score. Below `MIN_RETRIEVAL_CONFIDENCE` (0.35) the pipeline returns a
refusal naming the documents worth reading. A wrong-but-confident answer is
worse than an honest "I couldn't find it": the golden set is deliberately built
from answerable questions, so refusal quality is covered by unit tests instead.

**Deduplicate against the whole index, not the batch.**
Re-ingesting a corpus (or overlapping corpora) is caught by comparing new
embeddings against everything already stored at cosine > 0.95, which makes
ingestion idempotent. Deduplicating only within a batch is the common mistake
that doubles a store on the second run.

**Chunks record their embedding model.**
Drift detection compares the model stamped on stored chunks with the model in
use and warns loudly, because mixing embedding spaces destroys dense retrieval
silently.

## What the benchmark says

54 questions, `meta/llama-3.1-70b-instruct` judge, local `bge-base-en-v1.5`
embeddings: correctness 0.854, faithfulness 0.981, citation accuracy 0.963,
Recall@1 0.796, Recall@3 0.944, Recall@5 0.981, MRR 0.873, NDCG@5 0.952, mean
latency 5.1 s.

Read carefully, that profile says: **generation is not the bottleneck,
first-position retrieval is.** Recall@5 of 0.981 means the answer's passage is
almost always somewhere in the context; Recall@1 of 0.796 says it is often not
first, and the judge's retrieval-relevance score (0.691) is the lowest number on
the board. The highest-value changes are therefore retrieval-side:

1. **Contextual retrieval** — prefix each chunk with a short generated summary
   of how it fits its document, before embedding *and* before BM25 indexing.
   Published results report large failure-rate reductions from this step.
2. **Query transformation** — rewrite/expand short questions before retrieval;
   the golden questions are short, which is exactly where this helps.
3. **Chunk-size and strategy sweep** — `run_chunking_comparison` already exists;
   publishing a sweep table turns "recursive, 800 chars" from a default into a
   measured choice.

## Deliberately not built

GraphRAG, multi-agent orchestration, embedding fine-tuning and Kubernetes
packaging. Each adds surface area without changing the retrieval fundamentals
above, and the project is stronger with a small number of measured decisions
than a large number of unmeasured ones.
