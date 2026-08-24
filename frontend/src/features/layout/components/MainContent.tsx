"use client";

import { useCallback, useRef, useEffect, useMemo, memo } from "react";
import type { Project, ProjectFile, EditorSelection } from "@/app/lib/types";
import type { SaveStatus } from "@/features/editor/hooks/useFileSave";
import { Spinner } from "@/components/ui/Spinner";
import EditorPane from "@/features/editor/components/EditorPane";
import LiveCanvas from "@/features/editor/components/LiveCanvas";
import SplitPane from "@/components/ui/SplitPane";
import LandingPage from "@/features/layout/components/LandingPage";

type ViewMode = "preview" | "code" | "split";

interface MainContentProps {
  loading: boolean;
  error: string | null;
  activeProject: Project | null;
  files: ProjectFile[];
  onRetry: () => void;
  onFilesChange: (files: ProjectFile[]) => void;
  onSendPrompt: (prompt: string) => void;
  generating: boolean;
  onAddFile: (path: string) => void;
  onDeleteFile: (path: string) => void;
  onRenameFile: (oldPath: string, newPath: string) => void;
  activeFilePath: string | null;
  onActiveFileChange: (path: string | null) => void;
  saveStatus?: SaveStatus;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  onFigmaImportComplete?: (projectId: string) => void;
  onDesignUploadComplete?: (projectId: string) => void;
  onCreateFromTemplate?: (templateId: string) => void;
  isMobile?: boolean;
  dirtyFiles?: Set<string>;
  framework: "vanilla" | "react";
  onFrameworkChange: (framework: "vanilla" | "react") => void;
  /** Called when the user triggers "Edit with AI" from the editor context menu. */
  onEditWithAI?: (selection: EditorSelection) => void;
}

const VIEW_BUTTONS: { mode: ViewMode; label: string }[] = [
  { mode: "preview", label: "Preview" },
  { mode: "code", label: "Code" },
  { mode: "split", label: "Split" },
];

const MainContent = memo(function MainContent({
  loading,
  error,
  activeProject,
  files,
  onRetry,
  onFilesChange,
  onSendPrompt,
  generating,
  onAddFile,
  onDeleteFile,
  onRenameFile,
  activeFilePath,
  onActiveFileChange,
  saveStatus,
  viewMode,
  onViewModeChange,
  onFigmaImportComplete,
  onDesignUploadComplete,
  onCreateFromTemplate,
  isMobile,
  dirtyFiles,
  framework,
  onFrameworkChange,
  onEditWithAI,
}: MainContentProps) {
  const filesRef = useRef(files);

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  // Build a Map for O(1) file lookups instead of O(n) scans
  const filesMap = useMemo(() => new Map(files.map((f) => [f.path, f])), [files]);

  // When files change, auto-select the first file
  const effectiveActiveFile = useMemo(
    () => activeFilePath && filesMap.has(activeFilePath)
      ? activeFilePath
      : files[0]?.path ?? null,
    [activeFilePath, filesMap, files],
  );

  // When the active file is deleted, switch to the next available file
  useEffect(() => {
    if (activeFilePath && !filesMap.has(activeFilePath)) {
      onActiveFileChange(files[0]?.path ?? null);
    }
  }, [files]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFileContentChange = useCallback(
    (path: string, content: string) => {
      const currentFiles = filesRef.current;
      const updated = currentFiles.map((f) =>
        f.path === path ? { ...f, content } : f,
      );
      onFilesChange(updated);
    },
    [onFilesChange],
  );

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Spinner className="w-6 h-6" />
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

  // Active project — show editor + canvas with view mode toggle
  if (activeProject) {
    return (
      <div className="flex-1 flex flex-col min-h-0 overscroll-contain">
        {/* Project name bar with view mode toggle */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-sidebar">
          <span className="text-sm font-medium truncate">{activeProject.name}</span>
          {!isMobile && (
            <span className="text-xs text-text-secondary hidden sm:inline">
              {files.length} file{files.length !== 1 ? "s" : ""}
            </span>
          )}

          {/* Save status indicator */}
          {saveStatus && saveStatus !== "idle" && (
            <span className="flex items-center gap-1 text-xs">
              {saveStatus === "saving" && (
                <>
                  <span className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                  {!isMobile && <span className="text-accent hidden sm:inline">Saving...</span>}
                </>
              )}
              {saveStatus === "saved" && (
                <>
                  <span className="text-success animate-scale-in">✓</span>
                  {!isMobile && <span className="text-success hidden sm:inline">Saved</span>}
                </>
              )}
              {saveStatus === "error" && (
                <>
                  <span className="text-danger">✕</span>
                  {!isMobile && <span className="text-danger hidden sm:inline">Save failed</span>}
                </>
              )}
            </span>
          )}

          {/* Spacer */}
          <div className="flex-1" />

          {/* Export / Download ZIP */}
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/projects/${activeProject.id}/export`}
            download
            className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors touch-target"
            title="Download project as ZIP"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </a>

          {/* View mode toggle */}
          <div className="flex items-center gap-0.5 bg-surface rounded-lg p-0.5">
            {VIEW_BUTTONS.map(({ mode, label }) => {
              const isDisabled = isMobile && mode === "split";
              return (
                <button
                  key={mode}
                  onClick={() => onViewModeChange(mode)}
                  disabled={isDisabled}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors touch-target ${
                    viewMode === mode
                      ? "bg-accent text-white"
                      : isDisabled
                        ? "text-text-secondary/40 cursor-not-allowed"
                        : "text-text-secondary hover:text-foreground"
                  }`}
                  title={isDisabled ? "Split view is not available on mobile" : label}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Framework toggle */}
          {!isMobile && (
            <div className="flex items-center gap-0.5 bg-surface rounded-lg p-0.5">
              <button
                onClick={() => onFrameworkChange("vanilla")}
                className={`px-2 py-1 text-[11px] font-medium rounded-md transition-colors touch-target ${
                  framework === "vanilla"
                    ? "bg-accent text-white"
                    : "text-text-secondary hover:text-foreground"
                }`}
                title="Generate vanilla HTML/CSS/JS"
              >
                Vanilla
              </button>
              <button
                onClick={() => onFrameworkChange("react")}
                className={`px-2 py-1 text-[11px] font-medium rounded-md transition-colors touch-target ${
                  framework === "react"
                    ? "bg-accent text-white"
                    : "text-text-secondary hover:text-foreground"
                }`}
                title="Generate React JSX components"
              >
                React
              </button>
            </div>
          )}
        </div>

        {/* Content area based on view mode */}
        {viewMode === "split" ? (
          /* Split: editor left, canvas right with draggable divider */
          <SplitPane
            left={
              <EditorPane
                files={files}
                activeFilePath={effectiveActiveFile}
                onSelectFile={onActiveFileChange}
                onFileContentChange={handleFileContentChange}
                onAddFile={onAddFile}
                onDeleteFile={onDeleteFile}
                onRenameFile={onRenameFile}
                dirtyFiles={dirtyFiles}
                onEditWithAI={onEditWithAI}
              />
            }
            right={
              <LiveCanvas files={files} framework={framework} projectId={activeProject.id} />
            }
          />
        ) : viewMode === "code" ? (
          /* Code only: editor fills the area */
          <div className="flex-1 flex min-h-0">
            <EditorPane
              files={files}
              activeFilePath={effectiveActiveFile}
              onSelectFile={onActiveFileChange}
              onFileContentChange={handleFileContentChange}
              onAddFile={onAddFile}
              onDeleteFile={onDeleteFile}
              onRenameFile={onRenameFile}
              dirtyFiles={dirtyFiles}
              onEditWithAI={onEditWithAI}
            />
          </div>
        ) : (
          /* Preview only (default): canvas fills the area */
          <div className="flex-1 flex min-h-0">
            <LiveCanvas files={files} framework={framework} projectId={activeProject.id} />
          </div>
        )}
      </div>
    );
  }

  // Centered chat landing page — no project selected
  return (
    <LandingPage
      generating={generating}
      onSendPrompt={onSendPrompt}
      framework={framework}
      onFrameworkChange={onFrameworkChange}
      onFigmaImportComplete={onFigmaImportComplete}
      onDesignUploadComplete={onDesignUploadComplete}
      onCreateFromTemplate={onCreateFromTemplate}
    />
  );
});

export default MainContent;