"use client";

import { memo, useMemo, useState, useEffect, useRef, type ReactNode } from "react";
import type { ProjectFile } from "@/app/lib/types";

type ViewportPreset = "fluid" | "desktop" | "tablet" | "mobile";

const VIEWPORT_PRESETS: { key: ViewportPreset; label: string; width: number | null }[] = [
  { key: "fluid", label: "Fluid", width: null },
  { key: "desktop", label: "Desktop", width: 1280 },
  { key: "tablet", label: "Tablet", width: 768 },
  { key: "mobile", label: "Mobile", width: 375 },
];

interface PreviewShellProps {
  files: ProjectFile[];
  /** Build the HTML content from the debounced files. Return null to show the "no file" state, or an object with `error` for error state. */
  onBuildHtml: (files: ProjectFile[]) => string | { error: string } | null;
  /** Message to show when no suitable file is found */
  noFileMessage: string;
  /** Whether the required file type exists */
  hasRequiredFile: boolean;
  /** Extra content to render above the iframe (e.g. toolbar buttons) */
  toolbarExtra?: ReactNode;
}

/**
 * Shared preview shell that handles debounce, blob URL lifecycle, viewport presets,
 * and empty/error states. Used by both VanillaPreview and ReactPreview.
 */
const PreviewShell = memo(function PreviewShell({
  files,
  onBuildHtml,
  noFileMessage,
  hasRequiredFile,
  toolbarExtra,
}: PreviewShellProps) {
  const [viewport, setViewport] = useState<ViewportPreset>("fluid");
  const [debouncedFiles, setDebouncedFiles] = useState<ProjectFile[]>(files);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const blobUrlRef = useRef<string | null>(null);

  // Debounce file updates
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const isInitialLoad = debouncedFiles.length === 0 && files.length > 0;
    debounceRef.current = setTimeout(() => {
      setDebouncedFiles(files);
    }, isInitialLoad ? 0 : 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files]);

  const htmlContent = useMemo(() => onBuildHtml(debouncedFiles), [onBuildHtml, debouncedFiles]);

  // Track errors separately — not inside useMemo
  const previewError = htmlContent && typeof htmlContent === "object" && "error" in htmlContent
    ? (htmlContent as { error: string }).error
    : null;
  const previewHtml = htmlContent && typeof htmlContent === "string" ? htmlContent : null;

  // Create blob URL from htmlContent and revoke old ones
  useEffect(() => {
    if (!previewHtml) return;
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
    }
    const blob = new Blob([previewHtml], { type: "text/html" });
    blobUrlRef.current = URL.createObjectURL(blob);
    if (iframeRef.current) {
      iframeRef.current.src = blobUrlRef.current;
    }
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [previewHtml]);

  if (!hasRequiredFile) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-text-secondary">
        <p>{noFileMessage}</p>
      </div>
    );
  }

  if (previewError) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-danger">
        <p>Preview error: {previewError}</p>
      </div>
    );
  }

  const preset = VIEWPORT_PRESETS.find((p) => p.key === viewport)!;
  const isConstrained = preset.width !== null;

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-sidebar border-b border-border text-xs text-text-secondary">
        <div className="flex items-center gap-1">
          {VIEWPORT_PRESETS.map((p, i) => (
            <button
              key={p.key}
              onClick={() => setViewport(p.key)}
              className={`px-2 py-1 rounded-md text-xs font-medium transition-all ${
                viewport === p.key
                  ? "bg-accent text-white"
                  : "text-text-secondary hover:text-foreground hover:bg-surface"
              }`}
              style={{ animationDelay: `${i * 30}ms` }}
              title={`${p.label}${p.width ? ` — ${p.width}px` : ""}`}
            >
              {p.label}
            </button>
          ))}
          {toolbarExtra}
        </div>
        {isConstrained && (
          <span className="text-text-secondary hidden sm:inline">{preset.width}px</span>
        )}
      </div>

      {/* Iframe preview */}
      <div className="flex-1 flex items-stretch justify-center min-h-0 overflow-auto bg-preview-bg">
        <div
          className={`h-full transition-all duration-200 ${
            isConstrained ? "bg-white shadow-2xl my-0 flex-shrink-0" : "w-full"
          }`}
          style={
            isConstrained
              ? { width: `${preset.width}px`, maxWidth: "100%", minHeight: "100%" }
              : { width: "100%", minHeight: "100%" }
          }
        >
          <iframe
            ref={iframeRef}
            title="Preview"
            sandbox="allow-forms allow-modals allow-popups allow-same-origin allow-scripts"
            className="w-full h-full border-0"
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      </div>
    </div>
  );
});

export default PreviewShell;
