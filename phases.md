# Project Phases: RAG Pipeline

## Phase 1: Ingestion & Chunking (DONE)
- [x] Multi-format loaders (.md, .txt, .html, .pdf)
- [x] Switchable chunking strategies (fixed, recursive, semantic)
- [x] Corpus-aware near-duplicate detection (cosine similarity ≥ 0.95)

## Phase 2: Hybrid Retrieval (DONE)
- [x] Dense vector search (Qdrant)
- [x] Sparse keyword search (BM25)
- [x] Reciprocal Rank Fusion (RRF) integration
- [x] LLM-as-judge reranking

## Phase 3: Grounded Generation (DONE)
- [x] Context-grounded answer generation
- [x] Inline bracketed citations
- [x] Post-generation citation verification
- [x] Composite confidence scoring & refusal path
- [x] CLI and FastAPI front ends

## Phase 4: Evaluation Framework (PENDING)
- [ ] Create golden 50+ Q&A dataset in `tests/eval/`
- [ ] Implement evaluation runner for:
    - Answer correctness & faithfulness
    - Retrieval relevance (Hybrid vs Dense-only)
    - Citation accuracy
- [ ] Generate chunking-strategy comparison report
- [ ] Measure and validate PRD target metrics (Coverage, Refusal, Completeness, p95 Latency)
- [ ] Export structured JSON results and summary report

## Phase 5: Query Dashboard (PENDING)
- [ ] Implement Streamlit-based UI
- [ ] Connect to existing API endpoints (`/v1/ask`, `/v1/ingest`, `/v1/documents`)
- [ ] Add "Hybrid vs Dense-only" toggle (via `sparse_weight=0`)
- [ ] Display confidence scores and source citations visually

## Phase 6: Docker Packaging (PENDING)
- [ ] Create `Dockerfile` for API service
- [ ] Create `docker-compose.yml` bundling API + real Qdrant server
- [ ] Configure environment variable injection for secrets
- [ ] Transition to multi-worker `uvicorn` deployment

## Hardening & Technical Debt (PENDING)
- [ ] **Testing**:
    - [ ] Implement per-module unit tests for chunking and loaders
    - [ ] Implement E2E API tests using `TestClient`
    - [ ] Create a secret-gated live-API integration test for CI
- [ ] **Security**:
    - [ ] Implement API Key / Bearer token authentication
    - [ ] Fix path-traversal vulnerability in `/v1/ingest`
- [ ] **Operations**:
    - [ ] Replace `print()` statements with structured logging
    - [ ] Pin exact dependency versions in `requirements.txt` (lockfile)
