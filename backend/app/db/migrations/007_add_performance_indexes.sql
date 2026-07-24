-- Add performance indexes for common query patterns
-- These indexes speed up project listing, file lookups, and chat message retrieval.

-- Index for listing projects by user (most common query)
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects (user_id);

-- Index for ordering projects by updated_at (project list sorting)
CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects (updated_at DESC);

-- Composite index for file lookups by project (used in every project detail query)
CREATE INDEX IF NOT EXISTS idx_files_project_id ON files (project_id);

-- Composite index for file path lookups within a project (used in upsert/delete)
CREATE INDEX IF NOT EXISTS idx_files_project_path ON files (project_id, path);

-- Index for chat message ordering (used in get_chat_messages)
CREATE INDEX IF NOT EXISTS idx_chat_messages_project_created ON chat_messages (project_id, created_at);
