"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import type { Project, ProjectFile } from "../lib/types";
import type { SaveStatus } from "../hooks/useFileSave";
import EditorPane from "./EditorPane";
import LiveCanvas from "./LiveCanvas";
import FigmaImport from "./FigmaImport";
import DesignUpload from "./DesignUpload";

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
  activeFilePath: string | null;
  onActiveFileChange: (path: string | null) => void;
  showExplorer: boolean;
  onToggleExplorer: () => void;
  saveStatus?: SaveStatus;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  onFigmaImportComplete?: (projectId: string) => void;
  onDesignUploadComplete?: (projectId: string) => void;
}

const VIEW_BUTTONS: { mode: ViewMode; label: string }[] = [
  { mode: "preview", label: "Preview" },
  { mode: "code", label: "Code" },
  { mode: "split", label: "Split" },
];

export default function MainContent({
  loading,
  error,
  activeProject,
  files,
  onRetry,
  onFilesChange,
  onSendPrompt,
  generating,
  onAddFile,
  activeFilePath,
  onActiveFileChange,
  showExplorer,
  onToggleExplorer,
  saveStatus,
  viewMode,
  onViewModeChange,
  onFigmaImportComplete,
  onDesignUploadComplete,
}: MainContentProps) {
  const [promptValue, setPromptValue] = useState("");
  const promptTextareaRef = useRef<HTMLTextAreaElement>(null);
  const [showLandingMenu, setShowLandingMenu] = useState(false);
  const landingMenuRef = useRef<HTMLDivElement>(null);
  const landingFigmaRef = useRef<HTMLDivElement>(null);
  const landingDesignRef = useRef<HTMLDivElement>(null);
  const filesRef = useRef(files);
  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  // Build a Map for O(1) file lookups instead of O(n) scans
  const filesMap = useMemo(() => new Map(files.map((f) => [f.path, f])), [files]);

  // When files change, auto-select the first file
  const effectiveActiveFile = activeFilePath && filesMap.has(activeFilePath)
    ? activeFilePath
    : files[0]?.path ?? null;

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

  // Auto-resize landing prompt textarea
  useEffect(() => {
    const el = promptTextareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  }, [promptValue]);

  // Close landing add menu on outside click
  useEffect(() => {
    if (!showLandingMenu) return;
    const handleClick = (e: MouseEvent) => {
      if (landingMenuRef.current && !landingMenuRef.current.contains(e.target as Node)) {
        setShowLandingMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showLandingMenu]);

  const handleLandingSend = () => {
    const trimmed = promptValue.trim();
    if (!trimmed || generating) return;
    onSendPrompt(trimmed);
    setPromptValue("");
  };

  const handleLandingKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleLandingSend();
    }
  };

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

  // Active project — show editor + canvas with view mode toggle
  if (activeProject) {
    return (
      <div className="flex-1 flex flex-col min-h-0">
        {/* Project name bar with view mode toggle */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-sidebar/50">
          {/* Explorer toggle */}
          <button
            onClick={onToggleExplorer}
            className={`p-1 rounded-md transition-colors ${
              showExplorer
                ? "bg-surface text-foreground"
                : "text-text-secondary hover:text-foreground hover:bg-surface"
            }`}
            title={showExplorer ? "Collapse explorer" : "Show explorer"}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <span className="text-sm font-medium truncate">{activeProject.name}</span>
          <span className="text-xs text-text-secondary">
            {files.length} file{files.length !== 1 ? "s" : ""}
          </span>

          {/* Save status indicator */}
          {saveStatus && saveStatus !== "idle" && (
            <span className="flex items-center gap-1 text-xs">
              {saveStatus === "saving" && (
                <>
                  <span className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                  <span className="text-accent">Saving...</span>
                </>
              )}
              {saveStatus === "saved" && (
                <>
                  <span className="text-green-500">✓</span>
                  <span className="text-green-500">Saved</span>
                </>
              )}
              {saveStatus === "error" && (
                <>
                  <span className="text-danger">✕</span>
                  <span className="text-danger">Save failed</span>
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
            className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
            title="Download project as ZIP"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </a>

          {/* View mode toggle */}
          <div className="flex items-center gap-0.5 bg-surface rounded-lg p-0.5">
            {VIEW_BUTTONS.map(({ mode, label }) => (
              <button
                key={mode}
                onClick={() => onViewModeChange(mode)}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                  viewMode === mode
                    ? "bg-accent text-white shadow-sm"
                    : "text-text-secondary hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Content area based on view mode */}
        {viewMode === "split" ? (
          /* Split: editor left, canvas right */
          <div className="flex-1 flex min-h-0">
            <div className="flex-1 flex flex-col min-w-0 border-r border-border">
              <EditorPane
                files={files}
                activeFilePath={effectiveActiveFile}
                onSelectFile={onActiveFileChange}
                onFileContentChange={handleFileContentChange}
                onAddFile={onAddFile}
              />
            </div>
            <div className="flex-1 flex flex-col min-w-0">
              <LiveCanvas files={files} />
            </div>
          </div>
        ) : viewMode === "code" ? (
          /* Code only: editor fills the area */
          <div className="flex-1 flex min-h-0">
            <EditorPane
              files={files}
              activeFilePath={effectiveActiveFile}
              onSelectFile={onActiveFileChange}
              onFileContentChange={handleFileContentChange}
              onAddFile={onAddFile}
            />
          </div>
        ) : (
          /* Preview only (default): canvas fills the area */
          <div className="flex-1 flex min-h-0">
            <LiveCanvas files={files} />
          </div>
        )}
      </div>
    );
  }

  // Centered chat landing page — no project selected
  return (
    <div className="flex-1 flex items-center justify-center px-4">
      <div className="flex flex-col items-center gap-6 w-full max-w-xl">
        {/* Logo / Brand */}
        <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center">
          <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42" />
          </svg>
        </div>

        {/* Heading */}
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-foreground">What do you want to build?</h1>
          <p className="text-sm text-text-secondary mt-1">
            Describe your idea and AI will generate the code for you.
          </p>
        </div>

        {/* Prompt input */}
        <div className="w-full flex items-end gap-2 bg-input border border-border rounded-2xl px-4 py-3 focus-within:border-accent/50 focus-within:ring-1 focus-within:ring-accent/20 transition-all">
          <div className="relative" ref={landingMenuRef}>
            <button
              onClick={() => setShowLandingMenu((prev) => !prev)}
              className="flex-shrink-0 w-8 h-8 rounded-full bg-accent/10 hover:bg-accent/20 text-accent hover:text-accent-hover flex items-center justify-center transition-colors"
              title="Import or upload"
              aria-label="Import or upload"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
            </button>

            {showLandingMenu && (
              <div className="absolute bottom-full left-0 mb-2 w-56 bg-panel border border-border rounded-xl shadow-xl overflow-hidden z-50">
                <div className="p-3 space-y-1">
                  <p className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider px-1 pb-1">Import</p>
                  <button
                    onClick={() => { setShowLandingMenu(false); landingFigmaRef.current?.querySelector("button")?.click(); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-surface transition-colors text-left"
                  >
                    <svg className="w-4 h-4 text-accent flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12h-2v4H7v2h4v4h2v-4h4v-2h-4V8z" />
                    </svg>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-foreground">Figma Import</div>
                      <div className="text-[10px] text-text-secondary truncate">Paste a Figma URL to generate code</div>
                    </div>
                  </button>
                  <button
                    onClick={() => { setShowLandingMenu(false); landingDesignRef.current?.querySelector("button")?.click(); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-surface transition-colors text-left"
                  >
                    <svg className="w-4 h-4 text-accent flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-foreground">Design Upload</div>
                      <div className="text-[10px] text-text-secondary truncate">Upload an image to generate matching code</div>
                    </div>
                  </button>
                </div>
              </div>
            )}
          </div>

          <textarea
            ref={promptTextareaRef}
            value={promptValue}
            onChange={(e) => setPromptValue(e.target.value)}
            onKeyDown={handleLandingKeyDown}
            placeholder="e.g. Build a landing page with a hero section..."
            disabled={generating}
            className="flex-1 bg-transparent text-sm text-foreground placeholder-text-secondary resize-none outline-none focus-visible:outline-none max-h-[200px]"
          />
          <button
            onClick={handleLandingSend}
            disabled={!promptValue.trim() || generating}
            aria-label="Send prompt"
            className="flex-shrink-0 p-2 rounded-xl bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {generating ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>

        <p className="text-xs text-text-secondary text-center">
          AI-generated code may not always be perfect. Review and test before using.
        </p>
      </div>

      {/* Hidden toolbar buttons for landing page modals */}
      <div ref={landingFigmaRef} className="absolute -left-[9999px]" aria-hidden="true">
        <FigmaImport variant="toolbar" onImportComplete={onFigmaImportComplete} />
      </div>
      <div ref={landingDesignRef} className="absolute -left-[9999px]" aria-hidden="true">
        <DesignUpload projectId="" variant="toolbar" onUploadComplete={onDesignUploadComplete} />
      </div>
    </div>
  );
}
