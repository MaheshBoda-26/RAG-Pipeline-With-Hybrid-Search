-- Supabase Migration: Enable pgvector and create vector tables
-- Run this in Supabase Dashboard → SQL Editor

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Collections table (for multi-tenant support)
CREATE TABLE IF NOT EXISTS collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    user_id TEXT,
    embedding_dim INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Vectors table with pgvector
CREATE TABLE IF NOT EXISTS vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID REFERENCES collections(id) ON DELETE CASCADE,
    embedding vector(1024),  -- Match EMBEDDING_DIM from config
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Index for similarity search (IVFFlat with cosine distance)
CREATE INDEX IF NOT EXISTS vectors_embedding_ivfflat_idx
ON vectors USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 5. Full-text search column for BM25 replacement
ALTER TABLE vectors
ADD COLUMN IF NOT EXISTS fts tsvector
GENERATED ALWAYS AS (to_tsvector('english', payload->>'text')) STORED;

-- 6. GIN index for full-text search
CREATE INDEX IF NOT EXISTS vectors_fts_gin_idx
ON vectors USING GIN (fts);

-- 7. Enable Row Level Security (RLS) for multi-tenancy
ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE vectors ENABLE ROW LEVEL SECURITY;

-- 8. RLS Policies for collections
-- Users can only see their own collections
CREATE POLICY "Users can view own collections" ON collections
    FOR SELECT USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY "Users can insert own collections" ON collections
    FOR INSERT WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- 9. RLS Policies for vectors
-- Users can only access vectors in their collections
CREATE POLICY "Users can view own vectors" ON vectors
    FOR SELECT USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = current_setting('app.current_user_id', true)
        )
    );

CREATE POLICY "Users can insert own vectors" ON vectors
    FOR INSERT WITH CHECK (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = current_setting('app.current_user_id', true)
        )
    );

CREATE POLICY "Users can delete own vectors" ON vectors
    FOR DELETE USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = current_setting('app.current_user_id', true)
        )
    );

-- 10. Helper function to set current user context
CREATE OR REPLACE FUNCTION set_current_user_id(user_id TEXT)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_user_id', user_id, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 11. Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON collections TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON vectors TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION set_current_user_id(TEXT) TO anon, authenticated, service_role;

-- 12. Create initial collections for existing users
-- (Run after app creates users, or manually insert)
-- INSERT INTO collections (name, user_id, embedding_dim)
-- VALUES ('docs', 'default', 1024);