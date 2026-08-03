# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Development & Testing
- **Install dependencies**: `pip install -r requirements.txt`
- **Run smoke tests** (mocked LLM): `python tests/test_pipeline_smoke.py`
- **Ingest documents** (CLI): `python cli.py ingest ./sample_docs`
- **Ask question** (CLI): `python cli.py ask "your question"`
- **Run API server**: `uvicorn api:app --reload`

### API Interaction
- **Ingest**: `curl -X POST localhost:8000/v1/ingest -H 'content-type: application/json' -d '{"path": "./sample_docs"}'`
- **Ask**: `curl -X POST localhost:8000/v1/ask -H 'content-type: application/json' -d '{"question": "your question"}'`

## Architecture Overview

RAG pipeline with hybrid search (dense + sparse) and grounded generation.

### Core Flow
`sample_docs/` $\rightarrow$ `ingestion/` $\rightarrow$ `retrieval/` $\rightarrow$ `generation/` $\rightarrow$ Final Answer

### Component Breakdown
1. **Ingestion (`/ingestion`)**: 
   - `loaders.py`: Multi-format $\rightarrow$ plaintext.
   - `chunking.py`: Switchable strategies (`fixed`, `recursive`, `semantic`).
   - `dedup.py`: Corpus-aware near-duplicate removal (cosine similarity > 0.95).
2. **Retrieval (`/retrieval`)**:
   - **Hybrid Search**: Dense vectors (Qdrant) and Sparse search (BM25).
   - `fusion.py`: Reciprocal Rank Fusion (RRF) to combine results.
   - `reranker.py`: LLM-as-judge for final top-N ranking.
3. **Generation (`/generation`)**:
   - `generate.py`: Grounded answer generation using retrieved context.
   - `citations.py`: Extract $\rightarrow$ verify claims $\rightarrow$ calculate composite confidence score.
4. **Orchestration**:
   - `pipeline.py`: Main `RAGPipeline` class wiring all stages.
   - `cli.py` / `api.py`: Thin interfaces over the pipeline.

### Key Design Decisions
- **Embedded Qdrant**: Default storage in `./qdrant_data` (no separate server required).
- **Custom Splitters**: Implemented directly in `chunking.py` to avoid LangChain dependency.
- **Batched Reranking/Verification**: Multiple candidates/claims processed in single LLM calls for efficiency.
- **Composite Confidence**: Based on reranker scores, citation coverage, and judged completeness.
