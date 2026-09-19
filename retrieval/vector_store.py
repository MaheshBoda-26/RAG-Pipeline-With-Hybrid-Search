"""Dense vector storage via Qdrant.

Uses Qdrant's embedded mode (a local on-disk path, no server process) by
default so the project runs with zero extra infrastructure. Set QDRANT_URL
in .env to point at a real Qdrant server instead for a multi-process/
production deployment -- the interface is identical either way.

For embedded mode with multiple pipelines, we use a singleton client to
avoid file locking conflicts.
"""
from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ingestion.chunking import Chunk
from retrieval.sparse import tokenize as stokenize


# Singleton client for embedded mode to avoid concurrent access conflicts
_embedded_client: QdrantClient | None = None


def _get_embedded_client(path: str) -> QdrantClient:
    """Get or create singleton embedded Qdrant client."""
    global _embedded_client
    if _embedded_client is None:
        _embedded_client = QdrantClient(path=path, force_disable_check_same_thread=True)
    return _embedded_client


class QdrantVectorStore:
    def __init__(self, path: str, url: str, collection_name: str, embedding_dim: int, user_id: str | None = None):
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.user_id = user_id
        if url:
            self.client = QdrantClient(url=url)
        else:
            self.client = _get_embedded_client(path)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "default": qmodels.VectorParams(
                        size=self.embedding_dim,
                        distance=qmodels.Distance.COSINE,
                        quantization_config=qmodels.ScalarQuantization(
                            scalar=qmodels.ScalarQuantizationConfig(
                                type=qmodels.ScalarType.INT8,
                                quantile=0.99,
                                always_ram=False
                            )
                        )
                    )
                },
                sparse_vectors_config={
                    "bm25": qmodels.SparseVectorParams(modifier=qmodels.Modifier.IDF)
                },
            )
        else:
            # Check existing collection dims match; recreate if mismatch
            info = self.client.get_collection(self.collection_name)
            vectors_config = info.config.params.vectors
            # Handle both dict (named vectors) and single VectorParams
            size = None
            if isinstance(vectors_config, dict):
                # Named vectors - get the 'default' vector
                default_vec = vectors_config.get("default")
                if default_vec and hasattr(default_vec, "size"):
                    size = default_vec.size
            elif vectors_config and hasattr(vectors_config, "size"):
                # Single unnamed vector
                size = vectors_config.size
            if size != self.embedding_dim:
                import logging
                logging.getLogger(__name__).warning(
                    "Qdrant collection '%s' dimension mismatch (%s != %s). Recreating collection.",
                    self.collection_name, size, self.embedding_dim
                )
                self.client.delete_collection(self.collection_name)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "default": qmodels.VectorParams(
                            size=self.embedding_dim,
                            distance=qmodels.Distance.COSINE,
                            quantization_config=qmodels.ScalarQuantization(
                                scalar=qmodels.ScalarQuantizationConfig(
                                    type=qmodels.ScalarType.INT8,
                                    quantile=0.99,
                                    always_ram=False
                                )
                            )
                        )
                    },
                    sparse_vectors_config={
                        "bm25": qmodels.SparseVectorParams(modifier=qmodels.Modifier.IDF)
                    },
                )

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        points = [
            qmodels.PointStruct(
                id=chunk.id,
                vector={"default": embedding},
                payload={
                    "text": chunk.text,
                    "source": chunk.source,
                    "chunk_index": chunk.chunk_index,
                    "strategy": chunk.strategy,
                    "char_count": chunk.char_count,
                    "section_heading": chunk.section_heading,
                    "embedding_model": chunk.embedding_model,
                },
            )
            for chunk, embedding in zip(chunks, embeddings, strict=False)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """Returns a list of {id, score, payload} ranked by cosine similarity."""
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            using="default",
            limit=top_k,
            with_payload=True,
        ).points
        return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]

    def hybrid_query(
        self,
        query_embedding: list[float],
        question: str,
        top_k: int,
        source_filter: str | None = None,
        bm25: Any | None = None,
    ) -> list[dict]:
        """Hybrid search using dense vector query + Python BM25 + RRF fusion.

        When `source_filter` is set, the dense search is filtered AT THE
        DATABASE level (not after fusion) so scoped queries pull candidates
        only from the requested document instead of being crowded out by the
        rest of the corpus.

        Args:
            query_embedding: Dense vector for semantic search
            question: Query text for BM25 sparse search
            top_k: Number of results to return
            source_filter: Optional source filter to apply at Qdrant level
            bm25: Optional BM25Index instance to use for sparse search

        Returns:
            List of {id, score, payload} ranked by RRF fusion
        """
        # Step 1: Dense vector search via Qdrant, filtered at the DB level
        # when scoping to a single document.
        if source_filter:
            dense_results = self._filtered_query(query_embedding, source_filter, top_k * 2)
        else:
            dense_results = self.query(query_embedding, top_k * 2)

        # Step 2: Sparse BM25 keyword search, scoped to the same filter so
        # both legs of the hybrid search agree on the candidate universe.
        from rank_bm25 import BM25Okapi

        active_bm25 = bm25 if bm25 is not None else getattr(self, "bm25", None)
        if active_bm25 is not None:
            bm25_results = active_bm25.query(question, top_k * 2)
            if source_filter:
                bm25_results = [r for r in bm25_results if r["payload"].get("source") == source_filter]
        else:
            # Fallback: rebuild BM25 from stored chunks and query
            records = self.all_chunks(with_vectors=False)
            if source_filter:
                records = [r for r in records if r["payload"].get("source") == source_filter]
            corpus = [stokenize(r["payload"]["text"]) for r in records]
            built_bm25 = BM25Okapi(corpus) if corpus else None
            if built_bm25 is not None:
                scores = built_bm25.get_scores(stokenize(question))
                ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k * 2]
                bm25_results = [
                    {"id": records[i]["id"], "payload": records[i]["payload"], "score": float(scores[i])}
                    for i in ranked if scores[i] > 0
                ]
            else:
                bm25_results = []

        # Step 3: Fuse results using reciprocal rank fusion
        from retrieval.fusion import reciprocal_rank_fusion

        fused = reciprocal_rank_fusion(dense_results, bm25_results)

        # Step 4: Defensive post-filter (should be redundant now) and top_k
        if source_filter:
            fused = [r for r in fused if r["payload"].get("source") == source_filter]
        return fused[:top_k]

    def _filtered_query(self, query_embedding: list[float], source: str, top_k: int) -> list[dict]:
        """Dense query restricted to a single source document via a Qdrant
        payload filter. Returns the same shape as `query`."""
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            using="default",
            limit=top_k,
            with_payload=True,
            query_filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="source", match=qmodels.MatchValue(value=source))]
            ),
        ).points
        return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]

    def count(self) -> int:
        return self.client.count(collection_name=self.collection_name).count

    def all_chunks(self, with_vectors: bool = False) -> list[dict]:
        """Scroll the full collection. Used to (re)build the BM25 index, which
        Qdrant itself doesn't provide -- both indexes are built from the same
        source of truth so they can never drift out of sync. Also used to
        seed the dedup index with previously-ingested embeddings so repeat
        ingests of the same corpus are caught, not just in-batch duplicates."""
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=100_000,
            with_payload=True,
            with_vectors=with_vectors,
        )
        result = []
        for p in points:
            vec = None
            if with_vectors and p.vector:
                # Handle named vectors (dict with 'default' key) or single vector
                if isinstance(p.vector, dict):
                    vec = p.vector.get("default")
                else:
                    vec = p.vector
            result.append({"id": p.id, "payload": p.payload, "vector": vec})
        return result

    def delete_by_source(self, source: str) -> int:
        """Delete all points with matching source. Returns count deleted."""
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="source", match=qmodels.MatchValue(value=source))]
            ),
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )
        if not points:
            return 0
        point_ids = [p.id for p in points]
        self.client.delete(collection_name=self.collection_name, points_selector=qmodels.PointIdsList(points=point_ids))
        return len(point_ids)
