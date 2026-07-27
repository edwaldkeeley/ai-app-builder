-- Migration 008: Update file_type CHECK constraint to include all supported types
--
-- The original constraint only allowed: html, css, javascript, json, python, other
-- This migration adds: typescript, tsx, jsx, markdown, svg

ALTER TABLE files DROP CONSTRAINT IF EXISTS files_file_type_check;

ALTER TABLE files ADD CONSTRAINT files_file_type_check
  CHECK (file_type IN (
    'html', 'css', 'javascript', 'typescript', 'tsx', 'jsx',
    'json', 'python', 'markdown', 'svg', 'other'
  ));
