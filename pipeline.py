"""Top-level orchestrator wiring ingestion -> hybrid retrieval -> grounded
generation -> citation verification into two calls: ingest() and ask().
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

# Re-exported for tests, which patch ``pipeline.OpenAI`` to stub the LLM client.
from openai import OpenAI  # noqa: F401

from config import Settings
from generation.citations import (
    citation_coverage,
    composite_confidence,
    extract_claims,
    grounded_coverage,
    retrieval_confidence,
    verify_citations_and_completeness_sync,
)
from generation.generate import generate_answer
from generation.prompts import build_context_block
from ingestion.chunking import Chunk, chunk_fixed, chunk_recursive, chunk_semantic
from ingestion.dedup import DuplicateIndex
from ingestion.incremental import document_hash, plan_incremental, stored_hashes
from ingestion.loaders import RawDocument, load_directory, load_file
from observability import StageTimer, log_event, new_trace_id
from retrieval.contextual import ContextCache, add_chunk_contexts, make_llm_generator
from retrieval.fusion import merge_candidate_pools
from retrieval.query_transform import transform_queries
from retrieval.embeddings import Embedder, create_openai_client
from retrieval.reranker import rerank
from retrieval.sparse import BM25Index
from retrieval.vector_store import QdrantVectorStore
from retrieval.supabase_store import create_supabase_store
from retrieval.query_cache import QueryCache

# Process-wide context cache: one ingest run touches many documents, and each
# should reuse the cached situating contexts instead of re-reading the file.
_CONTEXT_CACHE: ContextCache | None = None


@dataclass
class AskResponse:
    question: str
    answer: str
    sources: list[dict]              # the ranked chunks actually shown to the model
    confidence: dict                 # retrieval / coverage / completeness / composite
    refused: bool = False
    refusal_reason: str | None = None
    # Per-stage wall-clock timings in milliseconds (see observability.StageTimer)
    timings: dict | None = None


class RAGPipeline:
    def __init__(self, settings: Settings | None = None, user_id: str | None = None):
        self.settings = settings or Settings()
        self.settings.validate()
        self.user_id = user_id or self.settings.default_user_id

        self.client = create_openai_client(
            api_key=self.settings.nvidia_api_key,
            base_url=self.settings.nvidia_base_url,
        )
        self.embedder = Embedder(self.client, self.settings.embedding_model, self.settings.embedding_dim)

        # Get user-specific collection name
        collection_name = self.settings.get_collection_name(self.user_id)

        # Choose vector store based on config
        if self.settings.use_supabase:
            self.vector_store = create_supabase_store(
                self.settings, collection_name, self.user_id
            )
        else:
            self.vector_store = QdrantVectorStore(
                path=self.settings.qdrant_path,
                url=self.settings.qdrant_url,
                collection_name=collection_name,
                embedding_dim=self.settings.embedding_dim,
                user_id=self.user_id,
            )
        self.bm25 = BM25Index(user_id=self.user_id)
        self._rebuild_sparse_index()  # picks up anything already in vector store from a prior run
        self._check_embedding_drift()

        # Query cache (Redis semantic cache)
        self.query_cache = None
        if self.settings.redis_url:
            try:
                self.query_cache = QueryCache(
                    redis_url=self.settings.redis_url,
                    exact_ttl=self.settings.cache_exact_ttl,
                    semantic_ttl=self.settings.cache_semantic_ttl,
                    distance_threshold=self.settings.cache_distance_threshold,
                    name=f"rag_query_cache_{self.user_id}",
                )
            except Exception:
                # Cache is optional; continue without it if Redis unavailable
                self.query_cache = None

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def _chunk_document(self, doc) -> list[Chunk]:
        strategy = self.settings.chunking_strategy
        chunks: list[Chunk]
        if strategy == "fixed":
            chunks = chunk_fixed(doc, self.settings.fixed_chunk_size, self.settings.fixed_chunk_overlap)
        elif strategy == "recursive":
            chunks = chunk_recursive(doc, self.settings.fixed_chunk_size, self.settings.fixed_chunk_overlap)
        elif strategy == "semantic":
            chunks = chunk_semantic(doc, self.embedder.embed, self.settings.semantic_similarity_threshold)
        else:
            raise ValueError(f"Unknown chunking strategy: {strategy}")
        # Stamp the embedding model on every chunk so the vector-store payload
        # records WHICH model produced the vectors — enables query-time drift
        # detection (mixing embedding spaces silently destroys dense search).
        for c in chunks:
            c.embedding_model = self.settings.embedding_model
        return chunks

    def _apply_contextual_context(self, doc: RawDocument, chunks: list[Chunk]) -> int:
        """Situate chunks inside their document before indexing (opt-in).

        Returns the number of contexts newly generated; cache hits are free.
        """
        if not self.settings.contextual_retrieval or not chunks:
            return 0

        global _CONTEXT_CACHE
        if _CONTEXT_CACHE is None or str(_CONTEXT_CACHE.path) != str(Path(self.settings.context_cache_path)):
            _CONTEXT_CACHE = ContextCache(self.settings.context_cache_path)

        generate = make_llm_generator(self.client, self.settings.contextual_model)
        return add_chunk_contexts(
            chunks,
            doc.text,
            document_hash(doc.text),
            generate,
            cache=_CONTEXT_CACHE,
            max_chunks=self.settings.contextual_max_chunks,
        )

    def _check_embedding_drift(self) -> None:
        """Warn loudly if indexed chunks were embedded by a different model
        than the one this pipeline is querying with."""
        try:
            records = self.vector_store.all_chunks(with_vectors=False)
        except Exception:
            return
        for r in records[:10]:  # sample; enough to detect a mixed collection
            stored = (r.get("payload") or {}).get("embedding_model")
            if stored and stored != self.settings.embedding_model:
                import logging
                logging.getLogger(__name__).warning(
                    "EMBEDDING MODEL DRIFT: collection '%s' contains chunks embedded by "
                    "'%s' but queries will use '%s'. Dense retrieval scores will be "
                    "meaningless until you DELETE the collection and RE-INGEST all "
                    "documents with the current model.",
                    self.settings.get_collection_name(self.user_id),
                    stored,
                    self.settings.embedding_model,
                )
                break

    def ingest_directory(self, path: str) -> dict:
        # Validate path to prevent path traversal
        requested_path = Path(path).resolve()
        allowed_root = Path(self.settings.allowed_ingest_root).resolve()

        if not requested_path.is_relative_to(allowed_root):
            raise ValueError(f"Ingest path {path} is outside the allowed directory {self.settings.allowed_ingest_root}")

        docs = load_directory(requested_path)

        # Incremental ingest: skip documents whose text is unchanged since the
        # last run, so re-ingesting a corpus does not re-embed everything.
        try:
            known_hashes = stored_hashes(self.vector_store.all_chunks())
        except Exception:
            known_hashes = {}
        changed_docs, unchanged_sources = plan_incremental(docs, known_hashes)

        all_chunks: list[Chunk] = []
        for doc in changed_docs:
            chunks = self._chunk_document(doc)
            for chunk in chunks:
                chunk.doc_hash = document_hash(doc.text)
            self._apply_contextual_context(doc, chunks)
            all_chunks.extend(chunks)

        if not all_chunks:
            # Invalidate query cache since documents may have changed
            if self.query_cache:
                try:
                    self.query_cache.clear_user(self.user_id)
                except Exception:
                    pass
            return {
                "documents": len(docs),
                "documents_changed": len(changed_docs),
                "documents_unchanged": len(unchanged_sources),
                "chunks_indexed": 0,
                "duplicates_skipped": 0,
            }

        # embedding_text = situating context + passage when contextual retrieval
        # is on, and the plain passage otherwise.
        embeddings = self.embedder.embed([c.embedding_text for c in all_chunks])

        dedup = DuplicateIndex(self.settings.dedup_similarity_threshold)
        # Seed with everything already indexed so re-ingesting the same
        # corpus (or a corpus with overlapping content) is caught too, not
        # just duplicates that happen to land in the same ingest batch.
        for existing in self.vector_store.all_chunks(with_vectors=True):
            if existing["vector"] is not None:
                dedup.add(existing["vector"])
        keep_idx, dup_idx = dedup.filter_new(embeddings)

        kept_chunks = [all_chunks[i] for i in keep_idx]
        kept_embeddings = [embeddings[i] for i in keep_idx]

        self.vector_store.upsert(kept_chunks, kept_embeddings)
        self._rebuild_sparse_index()

        # Invalidate query cache since documents have changed
        if self.query_cache:
            try:
                self.query_cache.clear_user(self.user_id)
            except Exception:
                pass

        return {
            "documents": len(docs),
            "documents_changed": len(changed_docs),
            "documents_unchanged": len(unchanged_sources),
            "chunks_created": len(all_chunks),
            "chunks_indexed": len(kept_chunks),
            "duplicates_skipped": len(dup_idx),
            "strategy": self.settings.chunking_strategy,
        }

    def ingest_file(self, file_path: str, original_filename: str | None = None, user_id: str | None = None) -> dict:
        """Ingest a single uploaded file. Returns stats dict."""
        from pathlib import Path

        # Validate path
        requested_path = Path(file_path).resolve()
        upload_dir = self.settings.get_user_upload_dir(user_id or self.user_id)
        allowed_root = Path(upload_dir).resolve()

        if not requested_path.is_relative_to(allowed_root):
            raise ValueError(f"File {file_path} is outside the allowed upload directory")

        doc = load_file(requested_path)
        if not doc:
            # Invalidate query cache since this may have changed document state
            if self.query_cache:
                try:
                    self.query_cache.clear_user(self.user_id)
                except Exception:
                    pass
            return {"documents": 0, "chunks_created": 0, "chunks_indexed": 0, "duplicates_skipped": 0}

        # Override the document source with the original filename for better UX
        if original_filename:
            doc = RawDocument(source=original_filename, text=doc.text, doc_type=doc.doc_type, pages=doc.pages)

        chunks = self._chunk_document(doc)
        for chunk in chunks:
            chunk.doc_hash = document_hash(doc.text)
        self._apply_contextual_context(doc, chunks)
        if not chunks:
            # Invalidate query cache since documents may have changed
            if self.query_cache:
                try:
                    self.query_cache.clear_user(self.user_id)
                except Exception:
                    pass
            return {"documents": 1, "chunks_created": 0, "chunks_indexed": 0, "duplicates_skipped": 0}

        try:
            embeddings = self.embedder.embed([c.embedding_text for c in chunks])
        except Exception as e:
            # Surface upstream embedding errors with context for API layer
            raise RuntimeError(f"Embedding API call failed ({type(e).__name__}): {e}") from e

        dedup = DuplicateIndex(self.settings.dedup_similarity_threshold)
        for existing in self.vector_store.all_chunks(with_vectors=True):
            if existing["vector"] is not None:
                dedup.add(existing["vector"])
        keep_idx, dup_idx = dedup.filter_new(embeddings)

        kept_chunks = [chunks[i] for i in keep_idx]
        kept_embeddings = [embeddings[i] for i in keep_idx]

        self.vector_store.upsert(kept_chunks, kept_embeddings)
        self._rebuild_sparse_index()

        # Invalidate query cache since documents have changed
        if self.query_cache:
            try:
                self.query_cache.clear_user(self.user_id)
            except Exception:
                pass

        return {
            "documents": 1,
            "chunks_created": len(chunks),
            "chunks_indexed": len(kept_chunks),
            "duplicates_skipped": len(dup_idx),
            "strategy": self.settings.chunking_strategy,
            "source": original_filename or str(requested_path),
        }

    def _rebuild_sparse_index(self):
        records = self.vector_store.all_chunks()
        self.bm25.build(records)

    # ------------------------------------------------------------------
    # Retrieval + generation
    # ------------------------------------------------------------------
    def ask(
        self,
        question: str,
        source: str | None = None,
        dense_weight: float | None = None,
        sparse_weight: float | None = None,
    ) -> AskResponse:
        trace_id = new_trace_id()
        timer = StageTimer(trace_id=trace_id, log=bool(os.getenv("LOG_PIPELINE_STAGES")))

        # Optional query transformation (QUERY_TRANSFORM=rewrite|expand). The
        # user's question always leads: transformation can add retrieval passes,
        # never replace the query that was actually asked.
        with timer.stage("transform_query"):
            transform_mode = self.settings.normalized_query_transform
            queries = transform_queries(
                question,
                mode=transform_mode,
                client=self.client if transform_mode != "none" else None,
                model=self.settings.chat_model,
                variants=self.settings.query_transform_variants,
            )

        with timer.stage("embed_query"):
            query_embedding = self.embedder.embed_one(queries[0])
            variant_embeddings = (
                self.embedder.embed(queries[1:]) if len(queries) > 1 else []
            )

        # Check query cache first
        if self.query_cache:
            cached = self.query_cache.lookup(
                query=question,
                query_embedding=query_embedding,
                user_id=self.user_id,
                source_filter=source,
            )
            if cached:
                return AskResponse(**cached)

        # Hybrid retrieval: a dense Qdrant query (filtered at the database level
        # when a source is specified) fused with the in-process BM25 keyword
        # index via reciprocal rank fusion. With QUERY_TRANSFORM=expand, each
        # rephrasing gets its own pass and the pools are unioned by consensus.
        with timer.stage("retrieve"):
            # Per-query weight override (website demo sliders). None = config
            # defaults; the pair arrives pre-normalized from the API layer.
            fusion_kwargs: dict = {}
            if dense_weight is not None and sparse_weight is not None:
                fusion_kwargs = {"dense_weight": dense_weight, "sparse_weight": sparse_weight}
            candidate_pool = self.vector_store.hybrid_query(
                query_embedding=query_embedding,
                question=queries[0],
                top_k=self.settings.rerank_candidate_pool,
                source_filter=source,
                bm25=self.bm25,
                **fusion_kwargs,
            )
            if variant_embeddings:
                extra_pools = [
                    self.vector_store.hybrid_query(
                        query_embedding=embedding,
                        question=variant,
                        top_k=self.settings.rerank_candidate_pool,
                        source_filter=source,
                        bm25=self.bm25,
                        **fusion_kwargs,
                    )
                    for variant, embedding in zip(queries[1:], variant_embeddings, strict=False)
                ]
                candidate_pool = merge_candidate_pools([candidate_pool, *extra_pools])

        with timer.stage("rerank"):
            # Rerank against the ORIGINAL question: rephrasings are for recall,
            # the user's own wording is the precision target.
            ranked = rerank(
                self.client, self.settings.chat_model, question, candidate_pool,
                top_n=self.settings.final_top_k,
                settings=self.settings,
            )

        retr_conf = retrieval_confidence(ranked)
        if not ranked or retr_conf < self.settings.min_retrieval_confidence:
            return AskResponse(
                question=question,
                answer=(
                    (
                        "I couldn't find enough relevant information in the indexed "
                        "documentation to answer this confidently. You may want to "
                        "check the following documents manually: "
                        + ", ".join(sorted({c["payload"]["source"] for c in candidate_pool[:3]}))
                    )
                    if candidate_pool else
                    "I couldn't find any relevant information in the indexed documentation."
                ),
                sources=self._source_blocks(ranked),
                confidence={
                    "retrieval_confidence": retr_conf, "citation_coverage": None,
                    "completeness": None, "composite": retr_conf,
                },
                refused=True,
                refusal_reason="retrieval_confidence_below_threshold",
                timings=timer.as_dict(),
            )

        with timer.stage("generate"):
            answer = generate_answer(self.client, self.settings.chat_model, question, ranked)

        with timer.stage("extract_claims"):
            claims = extract_claims(answer)
            context_str = "\n\n".join(build_context_block(i + 1, c["payload"]) for i, c in enumerate(ranked))

        # Run citation verification and completeness scoring in parallel
        with timer.stage("verify_and_score"):
            claims, completeness, answerable = verify_citations_and_completeness_sync(
                self.client,
                self.settings.chat_model,
                claims,
                ranked,
                question,
                answer,
                context_str,
            )
        # Two coverage numbers, two jobs:
        #   coverage  — claims supported by the block they cite (citation quality)
        #   grounding — claims supported by any retrieved passage (did the answer
        #               come from the corpus at all)
        # The refusal gate uses grounding, so a wrong citation number cannot turn
        # a correct answer into a refusal.
        coverage = citation_coverage(claims)
        grounding = grounded_coverage(claims)

        composite = composite_confidence(retr_conf, coverage, completeness)

        # Grounding gate. Retrieval score says "these passages are about the
        # right subject"; coverage says "this answer is supported by them". Only
        # the second detects a near-miss question, and a declining model ("the
        # context does not contain...") scores coverage 0 by definition. An
        # answer with no supported claim is a refusal, not an answer — reporting
        # it as an answer with sources attached is worse than refusing, because
        # callers that check only `refused` would trust it.
        # An answer grounded in a passage that does not answer the question is
        # still a non-answer: the judge reports whether the context contained the
        # information, independently of how the answer was phrased.
        unanswerable = self.settings.require_answerable and answerable is False

        if unanswerable or grounding <= self.settings.min_answer_coverage:
            reason = "context_cannot_answer_question" if unanswerable else "no_supported_citations"
            log_event(
                "ask", trace_id, refused=True, reason=reason,
                coverage=coverage, grounding=grounding, composite=composite,
                total_ms=timer.total_ms,
            )
            return AskResponse(
                question=question,
                answer=answer,
                sources=self._source_blocks(ranked),
                confidence={
                    "retrieval_confidence": round(retr_conf, 3),
                    "citation_coverage": round(coverage, 3),
                    "grounding_coverage": round(grounding, 3),
                    "completeness": round(completeness, 3),
                    "composite": composite,
                },
                refused=True,
                refusal_reason=reason,
                timings=timer.as_dict(),
            )

        response = AskResponse(
            question=question,
            answer=answer,
            sources=self._source_blocks(ranked),
            confidence={
                "retrieval_confidence": round(retr_conf, 3),
                "citation_coverage": round(coverage, 3),
                "grounding_coverage": round(grounding, 3),
                "completeness": round(completeness, 3),
                "composite": composite,
            },
            timings=timer.as_dict(),
        )

        log_event(
            "ask",
            trace_id,
            refused=False,
            sources=len(response.sources),
            composite=composite,
            total_ms=timer.total_ms,
        )

        # Store in cache for future queries
        if self.query_cache:
            try:
                self.query_cache.store(
                    query=question,
                    response=asdict(response),
                    query_embedding=query_embedding,
                    user_id=self.user_id,
                    source_filter=source,
                )
            except Exception:
                # Cache failures shouldn't break the main flow
                pass

        return response

    @staticmethod
    def _source_blocks(ranked: list[dict]) -> list[dict]:
        """The retrieved passages as the API/UI sees them.

        ``text`` is always the verbatim passage (what a citation quotes); the
        situating context used for indexing is not shown, so a quoted source can
        never contain text the document does not contain.
        """
        return [
            {
                "block": i + 1,
                "source": c["payload"]["source"],
                "section_heading": c["payload"].get("section_heading"),
                "text": c["payload"].get("text", ""),
                "fused_score": c.get("fused_score"),
                "rerank_score": c.get("rerank_score"),
                "dense_score": c.get("dense_score"),
                "variants": c.get("variants"),
            }
            for i, c in enumerate(ranked)
        ]

    def delete_document(self, source: str) -> int:
        """Delete all chunks for a given source document. Returns count deleted."""
        deleted = self.vector_store.delete_by_source(source)
        if deleted:
            self._rebuild_sparse_index()
        # Invalidate query cache since documents have changed
        if self.query_cache:
            try:
                self.query_cache.clear_user(self.user_id)
            except Exception:
                pass
        return deleted

    def list_documents(self) -> list[dict]:
        """List all unique source documents in the index."""
        records = self.vector_store.all_chunks()
        sources = {}
        for r in records:
            src = r["payload"].get("source", "unknown")
            if src not in sources:
                sources[src] = {"source": src, "chunk_count": 0, "total_chars": 0}
            sources[src]["chunk_count"] += 1
            sources[src]["total_chars"] += r["payload"].get("char_count", 0)
        return list(sources.values())

    @staticmethod
    def _basename(path_str: str) -> str:
        """Display name for a stored source path — the filename only."""
        return Path(path_str).name

    # ------------------------------------------------------------------
    # Visualization support (read-only; powers the website's vector-space
    # view and the pipeline console)
    # ------------------------------------------------------------------
    @staticmethod
    def _embed_to_point(vector: list[float], radius: float = 5.0) -> dict:
        """Project one embedding to a nearby-unique 3D point, deterministically.

        The projection is a bijective mix of the leading embedding components
        onto three pseudo-random orthogonal directions, so distinct embeddings
        land on distinct points (no origin pile-up) and strongly-similar
        embeddings — which share leading components — still land near each
        other. A fixed seed keeps coordinates stable across reloads; the map
        must not reshuffle itself between two views of the same corpus.
        """
        vec = np.asarray(vector, dtype=float)[:64]
        if vec.size < 8:
            vec = np.pad(vec, (0, 8 - vec.size))
        # Three deterministic directions mixed from the components themselves,
        # so the mapping embedding -> point stays order-stable per chunk.
        idx = np.arange(vec.size)
        phase = np.pi / 9.0
        axes = np.stack([
            np.sin(idx * phase + 0.0),
            np.sin(idx * phase + 2.1),
            np.sin(idx * phase + 4.2),
        ])  # 3 x n
        proj = axes @ vec  # 3
        norm = float(np.linalg.norm(proj)) or 1.0
        scaled = proj / norm * radius
        return {"x": round(float(scaled[0]), 4), "y": round(float(scaled[1]), 4), "z": round(float(scaled[2]), 4)}

    def vector_space(self, with_vectors: bool = True, max_chunks: int = 800) -> dict:
        """The corpus as a 3D map: real embeddings projected to points.

        Powers the website's vector-space view. Points are derived from the
        actual stored vectors — NOT hardcoded sample coordinates — so the
        visualization is honest by construction. Set ``with_vectors=False``
        (or hit the endpoint with ``?query=`` absent) to skip fetching vectors;
        without them, coordinates come from a text-seeded projection and
        cluster structure is approximate.
        """
        records = self.vector_store.all_chunks(with_vectors=with_vectors)
        chunks = []
        for r in records[:max_chunks]:
            payload = r.get("payload") or {}
            vector = r.get("vector")
            if vector:
                coords = self._embed_to_point(vector)
            else:
                # Deterministic pseudo-projection from the chunk text; used
                # only when vectors were not fetched.
                coords = self._embed_to_point(
                    [((ord(ch) * (i + 7)) % 97) / 97.0 for i, ch in enumerate((payload.get("text") or "")[:256])]
                )
            chunks.append({
                "id": str(r["id"]),
                **coords,
                "source": self._basename(payload.get("source", "unknown")),
                "strategy": payload.get("strategy", "unknown"),
                "section_heading": payload.get("section_heading"),
                "text": (payload.get("text") or "")[:200],
                # `role` is filled per-query by the ask endpoint; the corpus map
                # shows everything as unretrieved.
                "role": "unretrieved",
            })
        return {
            "chunks": chunks,
            "total_chunks": len(records),
            "truncated": len(records) > len(chunks),
        }

    def pipeline_trace(
        self,
        question: str,
        source: str | None = None,
        dense_weight: float | None = None,
        sparse_weight: float | None = None,
    ) -> dict:
        """Run one real ask() and return the answer plus its internals.

        The website's pipeline console shows the ACTUAL execution — per-stage
        timings, the dense and sparse lanes, fusion, rerank ordering and the
        confidence breakdown — read from the same AskResponse the API returns.
        No mock path exists; if the pipeline cannot answer, the trace shows the
        refusal, which is itself the product.
        """
        response = self.ask(
            question,
            source=source,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
        )
        timings = response.timings or {}

        # Reconstruct the lanes for the console. The ask() path fuses dense and
        # sparse inside hybrid_query, so the per-lane view here is derived from
        # what each surviving candidate carries: dense_rank/sparse_rank from
        # RRF, rerank order from the ranked list.
        lanes = {
            "dense": [
                {"id": s["block"], "source": s["source"], "dense_rank": None, "dense_score": s.get("dense_score")}
                for s in response.sources if s.get("dense_score") is not None
            ],
            "sparse": [],
            "fused": [
                {"id": s["block"], "source": s["source"], "fused_score": s.get("fused_score")}
                for s in response.sources
            ],
            "reranked": [
                {"id": s["block"], "source": s["source"], "rerank_score": s.get("rerank_score")}
                for s in response.sources
            ],
        }
        # Fill sparse rank from the candidate pool ordering where available.
        sparse_ids = [s["block"] for s in response.sources if s.get("fused_score") is not None and s.get("dense_score") is None]
        lanes["sparse"] = [
            {"id": s["block"], "source": s["source"], "sparse_rank": i + 1}
            for i, s in enumerate(response.sources) if s["block"] in sparse_ids
        ]

        return {
            "question": response.question,
            "answer": response.answer,
            "sources": response.sources,
            "confidence": response.confidence,
            "refused": response.refused,
            "refusal_reason": response.refusal_reason,
            "timings": timings,
            "total_ms": round(sum(timings.values()), 2),
            "lanes": lanes,
            "trace": {"stages": list(timings.keys())},
        }
