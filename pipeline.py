"""Top-level orchestrator wiring ingestion -> hybrid retrieval -> grounded
generation -> citation verification into two calls: ingest() and ask().
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from openai import OpenAI

from config import Settings
from generation.citations import (
    citation_coverage,
    composite_confidence,
    extract_claims,
    retrieval_confidence,
    score_completeness,
    verify_citations,
)
from generation.generate import generate_answer
from generation.prompts import build_context_block
from ingestion.chunking import Chunk, chunk_fixed, chunk_recursive, chunk_semantic
from ingestion.dedup import DuplicateIndex
from ingestion.loaders import load_directory
from retrieval.embeddings import Embedder
from retrieval.fusion import reciprocal_rank_fusion
from retrieval.reranker import rerank
from retrieval.sparse import BM25Index
from retrieval.vector_store import QdrantVectorStore


@dataclass
class AskResponse:
    question: str
    answer: str
    sources: list[dict]              # the ranked chunks actually shown to the model
    confidence: dict                 # retrieval / coverage / completeness / composite
    refused: bool = False
    refusal_reason: str | None = None


class RAGPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.settings.validate()

        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.embedder = Embedder(self.client, self.settings.embedding_model)
        self.vector_store = QdrantVectorStore(
            path=self.settings.qdrant_path,
            url=self.settings.qdrant_url,
            collection_name=self.settings.collection_name,
            embedding_dim=self.settings.embedding_dim,
        )
        self.bm25 = BM25Index()
        self._rebuild_sparse_index()  # picks up anything already in Qdrant from a prior run

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def _chunk_document(self, doc) -> list[Chunk]:
        strategy = self.settings.chunking_strategy
        if strategy == "fixed":
            return chunk_fixed(doc, self.settings.fixed_chunk_size, self.settings.fixed_chunk_overlap)
        if strategy == "recursive":
            return chunk_recursive(doc, self.settings.fixed_chunk_size, self.settings.fixed_chunk_overlap)
        if strategy == "semantic":
            return chunk_semantic(doc, self.embedder.embed, self.settings.semantic_similarity_threshold)
        raise ValueError(f"Unknown chunking strategy: {strategy}")

    def ingest_directory(self, path: str) -> dict:
        # Validate path to prevent path traversal
        requested_path = Path(path).resolve()
        allowed_root = Path(self.settings.allowed_ingest_root).resolve()

        if not requested_path.is_relative_to(allowed_root):
            raise ValueError(f"Ingest path {path} is outside the allowed directory {self.settings.allowed_ingest_root}")

        docs = load_directory(requested_path)
        all_chunks: list[Chunk] = []
        for doc in docs:
            all_chunks.extend(self._chunk_document(doc))

        if not all_chunks:
            return {"documents": len(docs), "chunks_indexed": 0, "duplicates_skipped": 0}

        embeddings = self.embedder.embed([c.text for c in all_chunks])

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

        return {
            "documents": len(docs),
            "chunks_created": len(all_chunks),
            "chunks_indexed": len(kept_chunks),
            "duplicates_skipped": len(dup_idx),
            "strategy": self.settings.chunking_strategy,
        }

    def _rebuild_sparse_index(self):
        records = self.vector_store.all_chunks()
        self.bm25.build(records)

    # ------------------------------------------------------------------
    # Retrieval + generation
    # ------------------------------------------------------------------
    def ask(self, question: str) -> AskResponse:
        query_embedding = self.embedder.embed_one(question)

        dense = self.vector_store.query(query_embedding, self.settings.dense_top_k)
        sparse = self.bm25.query(question, self.settings.sparse_top_k)

        fused = reciprocal_rank_fusion(
            dense, sparse,
            dense_weight=self.settings.dense_weight,
            sparse_weight=self.settings.sparse_weight,
            k=self.settings.rrf_k,
        )
        candidate_pool = fused[: self.settings.rerank_candidate_pool]

        ranked = rerank(
            self.client, self.settings.chat_model, question, candidate_pool,
            top_n=self.settings.final_top_k,
        )

        retr_conf = retrieval_confidence(ranked)
        if not ranked or retr_conf < self.settings.min_retrieval_confidence:
            return AskResponse(
                question=question,
                answer=(
                    "I couldn't find enough relevant information in the indexed "
                    "documentation to answer this confidently. You may want to "
                    "check the following documents manually: "
                    + ", ".join(sorted({c["payload"]["source"] for c in candidate_pool[:3]}))
                    if candidate_pool else
                    "I couldn't find any relevant information in the indexed documentation."
                ),
                sources=[
                    {
                        "block": i + 1,
                        "source": c["payload"]["source"],
                        "section_heading": c["payload"].get("section_heading"),
                        "fused_score": c.get("fused_score"),
                        "rerank_score": c.get("rerank_score"),
                    }
                    for i, c in enumerate(ranked)
                ],
                confidence={
                    "retrieval_confidence": retr_conf, "citation_coverage": None,
                    "completeness": None, "composite": retr_conf,
                },
                refused=True,
                refusal_reason="retrieval_confidence_below_threshold",
            )

        answer = generate_answer(self.client, self.settings.chat_model, question, ranked)

        claims = extract_claims(answer)
        claims = verify_citations(self.client, self.settings.chat_model, claims, ranked)
        coverage = citation_coverage(claims)

        context_str = "\n\n".join(build_context_block(i + 1, c["payload"]) for i, c in enumerate(ranked))
        completeness = score_completeness(self.client, self.settings.chat_model, question, answer, context_str)

        composite = composite_confidence(retr_conf, coverage, completeness)

        return AskResponse(
            question=question,
            answer=answer,
            sources=[
                {
                    "block": i + 1,
                    "source": c["payload"]["source"],
                    "section_heading": c["payload"].get("section_heading"),
                    "fused_score": c.get("fused_score"),
                    "rerank_score": c.get("rerank_score"),
                }
                for i, c in enumerate(ranked)
            ],
            confidence={
                "retrieval_confidence": round(retr_conf, 3),
                "citation_coverage": round(coverage, 3),
                "completeness": round(completeness, 3),
                "composite": composite,
            },
        )
