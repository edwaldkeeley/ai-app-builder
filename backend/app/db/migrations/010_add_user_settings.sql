-- 010_add_user_settings.sql
-- Add updated_at column to users table for tracking profile changes

ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
