# TODO: RAG Pipeline (Phases 4–6 + Hardening)

## Phase 4: Evaluation Framework
- [ ] Create golden Q&A dataset in `tests/eval/`
- [ ] Implement eval runner (faithfulness, correctness, relevance)
- [ ] Implement chunking-strategy comparison report
- [ ] Measure PRD targets: citation coverage, refusal rate, completeness, p95 latency
- [ ] Export structured JSON results

## Phase 5: Query Dashboard
- [ ] Build Streamlit UI
- [ ] Integrate with `/v1/ask`, `/v1/ingest`, `/v1/documents`
- [ ] Implement Hybrid vs Dense-only toggle
- [ ] Design visual confidence/citation display

## Phase 6: Docker Packaging
- [ ] Write `Dockerfile`
- [ ] Write `docker-compose.yml` (API + Qdrant server)
- [ ] Setup secrets injection via env
- [ ] Configure multi-worker `uvicorn`

## Hardening & Technical Debt
- [ ] Implement per-module unit tests (chunking, loaders)
- [ ] Implement `TestClient` E2E API tests
- [ ] Create secret-gated live-API CI test
- [ ] Implement API Key / Bearer token auth
- [ ] Patch `/v1/ingest` path-traversal vulnerability
- [ ] Migrate `print()` to structured logging
- [ ] Pin exact dependencies in `requirements.txt`
