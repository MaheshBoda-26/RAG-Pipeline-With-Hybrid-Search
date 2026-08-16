"""Dense vector storage via Qdrant.

Uses Qdrant's embedded mode (a local on-disk path, no server process) by
default so the project runs with zero extra infrastructure. Set QDRANT_URL
in .env to point at a real Qdrant server instead for a multi-process/
production deployment -- the interface is identical either way.
"""
from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ingestion.chunking import Chunk


class QdrantVectorStore:
    def __init__(self, path: str, url: str, collection_name: str, embedding_dim: int, user_id: str | None = None):
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.user_id = user_id
        if url:
            self.client = QdrantClient(url=url)
        else:
            self.client = QdrantClient(path=path)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.embedding_dim, distance=qmodels.Distance.COSINE
                ),
            )
        else:
            # Check existing collection dims match; recreate if mismatch
            info = self.client.get_collection(self.collection_name)
            if info.config.params.vectors.size != self.embedding_dim:
                self.client.delete_collection(self.collection_name)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=self.embedding_dim, distance=qmodels.Distance.COSINE
                    ),
                )

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        points = [
            qmodels.PointStruct(
                id=chunk.id,
                vector=embedding,
                payload={
                    "text": chunk.text,
                    "source": chunk.source,
                    "chunk_index": chunk.chunk_index,
                    "strategy": chunk.strategy,
                    "char_count": chunk.char_count,
                    "section_heading": chunk.section_heading,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """Returns a list of {id, score, payload} ranked by cosine similarity."""
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=top_k,
            with_payload=True,
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
        return [
            {"id": p.id, "payload": p.payload, "vector": (p.vector if with_vectors else None)}
            for p in points
        ]

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
