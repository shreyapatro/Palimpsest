-- Palimpsest schema
-- Run this after CREATE EXTENSION vector; on the target Postgres instance.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    id               BIGSERIAL PRIMARY KEY,
    content          TEXT NOT NULL,
    embedding        VECTOR(1024) NOT NULL,
    memory_type      TEXT NOT NULL CHECK (memory_type IN ('fact', 'preference', 'instruction')),
    trust_level      TEXT NOT NULL DEFAULT 'trusted' CHECK (trust_level IN ('trusted', 'untrusted')),
    status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded', 'archived', 'compressed')),
    supersedes_id    BIGINT REFERENCES memories(id),
    compressed_from  BIGINT[],
    reasoning_trace  TEXT,
    access_count     INT NOT NULL DEFAULT 0,
    decay_score      FLOAT NOT NULL DEFAULT 1.0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Approximate nearest neighbor index for cosine similarity search
CREATE INDEX IF NOT EXISTS memories_embedding_hnsw_idx
    ON memories USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS memories_status_idx ON memories (status);
CREATE INDEX IF NOT EXISTS memories_type_idx ON memories (memory_type);
