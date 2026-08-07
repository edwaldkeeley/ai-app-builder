"use client";

import { useState, useMemo, useRef, useEffect, useCallback, memo } from "react";
import type { ProjectFile } from "@/app/lib/types";
import { SkeletonExplorer } from "@/components/ui/Skeleton";
import FileRow, { buildTree, validateFilename } from "@/features/editor/components/FileRow";

interface FileExplorerProps {
  files: ProjectFile[];
  activeFilePath: string | null;
  onSelectFile: (path: string) => void;
  onAddFile: (path: string) => void;
  onDeleteFile: (path: string) => void;
  onRenameFile: (oldPath: string, newPath: string) => void;
  dirtyFiles?: Set<string>;
  loading?: boolean;
}

const FileExplorer = memo(function FileExplorer({
  files,
  activeFilePath,
  onSelectFile,
  onAddFile,
  onDeleteFile,
  onRenameFile,
  dirtyFiles,
  loading,
}: FileExplorerProps) {
  const [showRootNewFile, setShowRootNewFile] = useState(false);
  const [rootNewFileName, setRootNewFileName] = useState("");
  const [rootNewFileError, setRootNewFileError] = useState<string | null>(null);
  const rootNewFileInputRef = useRef<HTMLInputElement>(null);
  // Persist expanded/collapsed state for directories across re-renders
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());

  const tree = useMemo(() => buildTree(files), [files]);

  const onToggleDir = useCallback((path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (showRootNewFile) {
      setTimeout(() => rootNewFileInputRef.current?.focus(), 50);
    }
  }, [showRootNewFile]);

  const handleRootNewFileSubmit = () => {
    const trimmed = rootNewFileName.trim();
    if (!trimmed) {
      setShowRootNewFile(false);
      return;
    }
    const validationError = validateFilename(trimmed);
    if (validationError) {
      setRootNewFileError(validationError);
      return;
    }
    onAddFile(trimmed);
    setShowRootNewFile(false);
    setRootNewFileName("");
    setRootNewFileError(null);
  };

  const handleRootNewFileKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleRootNewFileSubmit();
    }
    if (e.key === "Escape") {
      setShowRootNewFile(false);
    }
  };

  const explorerPanel = (
    <div className="flex flex-col bg-sidebar border-r border-border w-56">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border min-h-[35px]">
        <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Code Files
        </span>
        <button
          onClick={() => setShowRootNewFile(true)}
          className="p-0.5 rounded hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
          title="New file"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* File count */}
      <div className="px-3 py-1 text-xs text-text-secondary border-b border-border">
        {files.length} file{files.length !== 1 ? "s" : ""}
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto py-1 overscroll-contain" role="tree" aria-label="File explorer">
        {loading && tree.length === 0 ? (
          <SkeletonExplorer />
        ) : tree.length === 0 ? (
          <div className="px-3 py-4 text-xs text-text-secondary text-center">
            <p>No files yet.</p>
            <button
              onClick={() => setShowRootNewFile(true)}
              className="mt-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
            >
              + Add File
            </button>
          </div>
        ) : (
          tree.map((node) => (
            <FileRow
              key={node.path}
              node={node}
              activeFilePath={activeFilePath}
              onSelectFile={onSelectFile}
              onDeleteFile={onDeleteFile}
              onRenameSubmit={onRenameFile}
              onAddFile={onAddFile}
              dirtyFiles={dirtyFiles}
              expandedDirs={expandedDirs}
              onToggleDir={onToggleDir}
            />
          ))
        )}

        {/* Root-level new file input */}
        {showRootNewFile && (
          <div className="flex flex-col px-2 py-0.5" style={{ paddingLeft: "12px" }}>
            <div className="flex items-center gap-1">
              <svg className="w-3 h-3 flex-shrink-0 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <input
                ref={rootNewFileInputRef}
                type="text"
                value={rootNewFileName}
                onChange={(e) => { setRootNewFileName(e.target.value); setRootNewFileError(null); }}
                onKeyDown={handleRootNewFileKeyDown}
                onBlur={() => {
                  if (!rootNewFileName.trim()) setShowRootNewFile(false);
                }}
                placeholder="filename.html"
                className="flex-1 bg-input border border-border rounded px-1 py-0 text-xs text-foreground placeholder-text-secondary outline-none focus:border-accent/50 min-w-0"
              />
            </div>
            {rootNewFileError && (
              <span className="text-xs text-danger mt-0.5" role="alert">{rootNewFileError}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );

  return explorerPanel;
});

export default FileExplorer;
