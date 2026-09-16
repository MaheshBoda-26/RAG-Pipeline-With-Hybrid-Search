-- Fix-plan migration (Sept 2026): resize pgvector column for the new
-- embedding model and create the missing match_vectors RPC.
--
-- Context: EMBEDDING_MODEL moved from BAAI/bge-base-en-v1.5 (768d, 404s on
-- NVIDIA) to nvidia/nemotron-3-embed-1b (2048d, live). The vectors table was
-- created with `embedding vector(768)`, so upserts of 2048-dim vectors fail
-- with "expected 768 dimensions, not 2048".
--
-- Safe to re-run: idempotent statements only. Existing rows were already
-- wiped for user_default (re-ingested with the new model); other collections
-- with old 768-dim rows will FAIL the ALTER if non-empty — delete or migrate
-- those collections' rows first (they are stale test data).

-- 1. Drop the old IVFFlat index (required before changing column type)
DROP INDEX IF EXISTS vectors_embedding_ivfflat_idx;

-- 2. Resize the embedding column to 2048 dims
-- (typmod change; fails if any row has non-2048-dim data)
ALTER TABLE vectors
    ALTER COLUMN embedding TYPE vector(2048);

-- 3. Recreate the cosine similarity index for the new dimension
CREATE INDEX IF NOT EXISTS vectors_embedding_ivfflat_idx
ON vectors USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 4. Create the match_vectors RPC the store has been trying to call
-- (fixes PGRST202 "Could not find the function public.match_vectors")
CREATE OR REPLACE FUNCTION match_vectors (
    query_embedding vector(2048),
    match_collection_id uuid,
    match_count int
)
RETURNS TABLE (
    id uuid,
    similarity float,
    payload jsonb
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        v.id,
        1 - (v.embedding <=> query_embedding) AS similarity,
        v.payload
    FROM vectors v
    WHERE v.collection_id = match_collection_id
    ORDER BY v.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- 5. Grant execute to the service role / anon as configured by Supabase
GRANT EXECUTE ON FUNCTION match_vectors(vector(2048), uuid, int) TO service_role, anon;
