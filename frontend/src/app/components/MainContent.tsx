"use client";

import { useState, useCallback } from "react";
import type { Project, ProjectFile } from "../lib/types";
import EditorPane from "./EditorPane";
import LiveCanvas from "./LiveCanvas";

interface MainContentProps {
  loading: boolean;
  error: string | null;
  activeProject: Project | null;
  files: ProjectFile[];
  onRetry: () => void;
  onCreateProject: () => void;
  creating: boolean;
  onFilesChange: (files: ProjectFile[]) => void;
}

export default function MainContent({
  loading,
  error,
  activeProject,
  files,
  onRetry,
  onCreateProject,
  creating,
  onFilesChange,
}: MainContentProps) {
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);

  // When files change, auto-select the first file
  const effectiveActiveFile = activeFilePath && files.find((f) => f.path === activeFilePath)
    ? activeFilePath
    : files[0]?.path ?? null;

  const handleFileContentChange = useCallback(
    (path: string, content: string) => {
      const updated = files.map((f) =>
        f.path === path ? { ...f, content } : f,
      );
      onFilesChange(updated);
    },
    [files, onFilesChange],
  );

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-text-secondary">Connecting to server...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 max-w-sm text-center px-4">
          <div className="w-12 h-12 rounded-full bg-danger/10 flex items-center justify-center">
            <svg className="w-6 h-6 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-foreground">Connection Error</p>
          <p className="text-xs text-text-secondary">{error}</p>
          <button
            onClick={onRetry}
            className="px-4 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Active project — show editor + canvas
  if (activeProject) {
    return (
      <div className="flex-1 flex flex-col min-h-0">
        {/* Project name bar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-sidebar/50">
          <span className="text-sm font-medium truncate">{activeProject.name}</span>
          <span className="text-xs text-text-secondary">
            {files.length} file{files.length !== 1 ? "s" : ""}
          </span>
        </div>
        {/* Editor + Canvas split */}
        <div className="flex-1 flex min-h-0">
          <div className="flex-1 flex flex-col min-w-0 border-r border-border">
            <EditorPane
              files={files}
              activeFilePath={effectiveActiveFile}
              onSelectFile={setActiveFilePath}
              onFileContentChange={handleFileContentChange}
            />
          </div>
          <div className="flex-1 flex flex-col min-w-0">
            <LiveCanvas files={files} />
          </div>
        </div>
      </div>
    );
  }

  // Empty state — no projects
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-center px-4">
        <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center">
          <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </div>
        <p className="text-sm font-medium text-foreground">No projects yet</p>
        <p className="text-xs text-text-secondary max-w-xs">
          Create your first project to start building with AI.
        </p>
        <button
          onClick={onCreateProject}
          disabled={creating}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {creating ? "Creating..." : "Create Project"}
        </button>
      </div>
    </div>
  );
}
