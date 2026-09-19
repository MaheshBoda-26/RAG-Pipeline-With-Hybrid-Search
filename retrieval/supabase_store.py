"""Dense vector storage via Supabase REST API.

Uses Supabase Python client (supabase-py) to interact with PostgreSQL via REST API.
This avoids pooler connection issues and is the recommended approach for Supabase.

Requires:
- Supabase project with pgvector extension enabled
- Tables created via migration script
"""

from __future__ import annotations

from typing import Any, List, Optional

from supabase import create_client, Client
from ingestion.chunking import Chunk


class SupabaseVectorStore:
    """Supabase-backed vector store using REST API."""

    def __init__(
        self,
        url: str,
        service_key: str,
        collection_name: str,
        embedding_dim: int,
        user_id: Optional[str] = None,
    ):
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.user_id = user_id
        self.client: Client = create_client(url, service_key)
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        # Check if collection exists
        result = self.client.table("collections").select("id").eq("name", self.collection_name).execute()

        if result.data:
            self.collection_id = result.data[0]["id"]
        else:
            # Create new collection
            result = self.client.table("collections").insert({
                "name": self.collection_name,
                "user_id": self.user_id,
                "embedding_dim": self.embedding_dim,
            }).execute()
            self.collection_id = result.data[0]["id"]

    def upsert(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        """Insert or update vectors."""
        if not chunks:
            return

        # Prepare data for batch insert
        data = []
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            # Convert embedding to string format for pgvector
            vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
            payload = {
                "text": chunk.text,
                "source": chunk.source,
                "chunk_index": chunk.chunk_index,
                "strategy": chunk.strategy,
                "char_count": chunk.char_count,
                "section_heading": chunk.section_heading,
                "embedding_model": chunk.embedding_model,
            }
            data.append({
                "id": chunk.id,
                "collection_id": self.collection_id,
                "embedding": vec_str,
                "payload": payload,
            })

        # Batch upsert using Supabase client
        # Supabase doesn't have native upsert, so we use insert with on_conflict
        self.client.table("vectors").upsert(data, on_conflict="id").execute()

    def query(self, query_embedding: List[float], top_k: int) -> List[dict]:
        """Return top-k similar vectors by cosine similarity using RPC."""
        vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Use RPC for similarity search
        # We need to create a similarity search function in Supabase first
        try:
            result = self.client.rpc("match_vectors", {
                "query_embedding": vec_str,
                "match_collection_id": self.collection_id,
                "match_count": top_k,
            }).execute()

            if result.data:
                return [{
                    "id": row["id"],
                    "score": row["similarity"],
                    "payload": row["payload"],
                } for row in result.data]
        except Exception as e:
            print(f"WARNING: RPC match_vectors failed for collection {self.collection_id} ({e}). Falling back to O(n) Python similarity computation — this will be slow for large datasets. Run supabase_migration.sql to create the RPC function.")
            # Fallback: fetch all and compute locally (for small datasets)

        # Fallback: fetch all vectors and compute similarity in Python
        result = self.client.table("vectors").select("id, payload, embedding").eq("collection_id", self.collection_id).execute()

        if not result.data:
            return []

        # Compute cosine similarity
        import numpy as np
        query_vec = np.array(query_embedding)
        results = []
        for row in result.data:
            # Parse embedding string to list
            emb_str = row["embedding"]
            if isinstance(emb_str, str):
                emb_list = [float(x) for x in emb_str.strip("[]").split(",")]
            else:
                emb_list = emb_str
            emb_vec = np.array(emb_list)

            # Cosine similarity
            sim = np.dot(query_vec, emb_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(emb_vec))
            results.append({
                "id": row["id"],
                "score": float(sim),
                "payload": row["payload"],
            })

        # Sort by similarity descending and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def count(self) -> int:
        """Count vectors in collection."""
        result = self.client.table("vectors").select("id", count="exact").eq("collection_id", self.collection_id).execute()
        return result.count or 0

    def all_chunks(self, with_vectors: bool = False) -> List[dict]:
        """Scroll all chunks for BM25 rebuild and dedup seeding."""
        select_cols = "id, payload" + (", embedding" if with_vectors else "")
        result = self.client.table("vectors").select(select_cols).eq("collection_id", self.collection_id).order("created_at").execute()

        results = []
        for row in result.data:
            vec = None
            if with_vectors and row.get("embedding"):
                emb_str = row["embedding"]
                if isinstance(emb_str, str):
                    vec = [float(x) for x in emb_str.strip("[]").split(",")]
                else:
                    vec = emb_str
            results.append({
                "id": row["id"],
                "payload": row["payload"],
                "vector": vec,
            })
        return results

    def hybrid_query(
        self,
        query_embedding: List[float],
        question: str,
        top_k: int,
        source_filter: Optional[str] = None,
        bm25: Optional[Any] = None,
        dense_weight: Optional[float] = None,
        sparse_weight: Optional[float] = None,
    ) -> List[dict]:
        """Hybrid search combining Supabase dense vector query + BM25 + RRF fusion."""
        # Dense search via Supabase
        dense_results = self.query(query_embedding, top_k * 2)

        # Sparse search via BM25
        if bm25 is not None:
            bm25_results = bm25.query(question, top_k * 2)
        else:
            from retrieval.sparse import tokenize as stokenize
            from rank_bm25 import BM25Okapi
            records = self.all_chunks(with_vectors=False)
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

        from retrieval.fusion import reciprocal_rank_fusion

        fusion_kwargs: dict = {}
        if dense_weight is not None and sparse_weight is not None:
            fusion_kwargs = {"dense_weight": dense_weight, "sparse_weight": sparse_weight}
        fused = reciprocal_rank_fusion(dense_results, bm25_results, **fusion_kwargs)

        if source_filter:
            fused = [r for r in fused if r["payload"].get("source") == source_filter]

        return fused[:top_k]

    def delete_by_source(self, source: str) -> int:
        """Delete all vectors for a source document."""
        result = self.client.table("vectors").delete().eq("collection_id", self.collection_id).eq("payload->>source", source).execute()
        return len(result.data) if result.data else 0


def create_supabase_store(settings, collection_name: str, user_id: Optional[str] = None) -> SupabaseVectorStore:
    """Create SupabaseVectorStore from settings."""
    if not settings.supabase_url or not settings.supabase_service_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured")
    if not settings.use_supabase:
        raise ValueError("USE_SUPABASE is false")
    return SupabaseVectorStore(
        url=settings.supabase_url,
        service_key=settings.supabase_service_key,
        collection_name=collection_name,
        embedding_dim=settings.embedding_dim,
        user_id=user_id,
    )