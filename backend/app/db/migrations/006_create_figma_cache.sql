CREATE TABLE IF NOT EXISTS figma_cache (
    file_key    VARCHAR(255) PRIMARY KEY,
    data        JSONB NOT NULL,
    cached_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ttl_seconds INTEGER NOT NULL DEFAULT 300
);

CREATE INDEX IF NOT EXISTS idx_figma_cache_cached_at ON figma_cache (cached_at);
