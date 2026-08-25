"""Dense vector storage via Supabase (PostgreSQL + pgvector).

Uses Supabase as the vector database backend with pgvector extension.
Supports multi-tenancy via Row Level Security (RLS) or collection-based isolation.

Requires:
- Supabase project with pgvector extension enabled
- Connection string with service role key for writes
"""

from __future__ import annotations

import os
import uuid
from typing import Optional
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import SimpleConnectionPool

from ingestion.chunking import Chunk


class SupabaseVectorStore:
    """Supabase-backed vector store with pgvector for similarity search."""

    def __init__(
        self,
        db_url: str,
        collection_name: str,
        embedding_dim: int,
        user_id: Optional[str] = None,
        min_connections: int = 1,
        max_connections: int = 5,
    ):
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.user_id = user_id

        # Connection pool
        self.pool = SimpleConnectionPool(min_connections, max_connections, db_url)
        self._ensure_schema()

    @contextmanager
    def _conn(self):
        """Get a connection from the pool."""
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def _ensure_schema(self):
        """Create tables and indexes if they don't exist."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                # Enable pgvector extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # Collections table for multi-tenant support
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS collections (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name TEXT UNIQUE NOT NULL,
                        user_id TEXT,
                        embedding_dim INTEGER NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)

                # Create or get collection
                cur.execute("""
                    INSERT INTO collections (name, user_id, embedding_dim)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        embedding_dim = EXCLUDED.embedding_dim
                    RETURNING id;
                """, (self.collection_name, self.user_id, self.embedding_dim))
                self.collection_id = cur.fetchone()[0]

                # Vectors table with pgvector
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS vectors (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        collection_id UUID REFERENCES collections(id) ON DELETE CASCADE,
                        embedding vector({self.embedding_dim}),
                        payload JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)

                # Index for similarity search (IVFFlat)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS vectors_embedding_ivfflat_idx
                    ON vectors USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                """)

                # Full-text search index for BM25 replacement
                cur.execute("""
                    ALTER TABLE vectors
                    ADD COLUMN IF NOT EXISTS fts tsvector
                    GENERATED ALWAYS AS (to_tsvector('english', payload->>'text')) STORED;
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS vectors_fts_gin_idx
                    ON vectors USING GIN (fts);
                """)

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Insert or update vectors."""
        if not chunks:
            return

        with self._conn() as conn:
            with conn.cursor() as cur:
                data = []
                for chunk, embedding in zip(chunks, embeddings):
                    # Convert embedding list to pgvector format
                    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
                    payload = {
                        "text": chunk.text,
                        "source": chunk.source,
                        "chunk_index": chunk.chunk_index,
                        "strategy": chunk.strategy,
                        "char_count": chunk.char_count,
                        "section_heading": chunk.section_heading,
                    }
                    data.append((
                        str(uuid.uuid4()),
                        self.collection_id,
                        vec_str,
                        payload,
                    ))

                execute_values(
                    cur,
                    """
                    INSERT INTO vectors (id, collection_id, embedding, payload)
                    VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        payload = EXCLUDED.payload
                    """,
                    data,
                    template="(%s, %s, %s::vector, %s::jsonb)",
                    page_size=100,
                )

    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """Return top-k similar vectors by cosine similarity."""
        vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, payload, embedding <=> %s::vector AS distance
                    FROM vectors
                    WHERE collection_id = %s
                    ORDER BY distance ASC
                    LIMIT %s
                """, (vec_str, str(self.collection_id), top_k))

                results = []
                for row in cur.fetchall():
                    results.append({
                        "id": str(row["id"]),
                        "score": 1.0 - float(row["distance"]),  # Convert distance to similarity
                        "payload": row["payload"],
                    })
                return results

    def count(self) -> int:
        """Count vectors in collection."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM vectors WHERE collection_id = %s",
                    (str(self.collection_id),)
                )
                return cur.fetchone()[0]

    def all_chunks(self, with_vectors: bool = False) -> list[dict]:
        """Scroll all chunks for BM25 rebuild and dedup seeding."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if with_vectors:
                    cur.execute("""
                        SELECT id, payload, embedding
                        FROM vectors
                        WHERE collection_id = %s
                        ORDER BY created_at
                    """, (str(self.collection_id),))
                else:
                    cur.execute("""
                        SELECT id, payload
                        FROM vectors
                        WHERE collection_id = %s
                        ORDER BY created_at
                    """, (str(self.collection_id),))

                results = []
                for row in cur.fetchall():
                    vec = None
                    if with_vectors and row.get("embedding"):
                        # pgvector returns as list
                        vec = list(row["embedding"]) if isinstance(row["embedding"], (list, tuple)) else None
                    results.append({
                        "id": str(row["id"]),
                        "payload": row["payload"],
                        "vector": vec,
                    })
                return results

    def delete_by_source(self, source: str) -> int:
        """Delete all vectors for a source document."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM vectors
                    WHERE collection_id = %s AND payload->>'source' = %s
                    RETURNING id
                """, (str(self.collection_id), source))
                deleted = cur.rowcount
                return deleted

    def close(self):
        """Close the connection pool."""
        self.pool.closeall()


# Factory function for easy instantiation from settings
def create_supabase_store(settings, collection_name: str, user_id: Optional[str] = None) -> SupabaseVectorStore:
    """Create SupabaseVectorStore from settings."""
    if not settings.supabase_db_url:
        raise ValueError("SUPABASE_DB_URL not configured")
    if not settings.use_supabase:
        raise ValueError("USE_SUPABASE is false")
    return SupabaseVectorStore(
        db_url=settings.supabase_db_url,
        collection_name=collection_name,
        embedding_dim=settings.embedding_dim,
        user_id=user_id,
    )