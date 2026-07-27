-- Migration 009: Add framework column to projects table
--
-- Tracks whether a project uses "vanilla" HTML/CSS/JS or "react" JSX.

ALTER TABLE projects ADD COLUMN IF NOT EXISTS framework VARCHAR(20) NOT NULL DEFAULT 'vanilla'
  CHECK (framework IN ('vanilla', 'react'));
