"use client";

import { memo, useMemo, useState, useEffect, useRef } from "react";
import {
  SandpackProvider,
  SandpackPreview,
  useSandpack,
} from "@codesandbox/sandpack-react";
import type { ProjectFile } from "../lib/types";

interface LiveCanvasProps {
  files: ProjectFile[];
  framework?: "vanilla" | "react";
}

type ViewportPreset = "fluid" | "desktop" | "tablet" | "mobile";

const VIEWPORT_PRESETS: { key: ViewportPreset; label: string; width: number | null }[] = [
  { key: "fluid", label: "Fluid", width: null },
  { key: "desktop", label: "Desktop", width: 1280 },
  { key: "tablet", label: "Tablet", width: 768 },
  { key: "mobile", label: "Mobile", width: 375 },
];

// ── Convert ProjectFile[] to Sandpack's file format ──────────

function toSandpackFiles(files: ProjectFile[]): Record<string, { code: string }> {
  const result: Record<string, { code: string }> = {};
  for (const f of files) {
    result[f.path] = { code: f.content };
  }
  return result;
}

// ── File syncer: pushes file changes into Sandpack ───────────

function FileSyncer({ files }: { files: ProjectFile[] }) {
  const { sandpack } = useSandpack();
  const filesRef = useRef(files);
  const sandpackRef = useRef(sandpack);

  // Keep refs in sync (runs after every render, no deps — intentional)
  useEffect(() => {
    filesRef.current = files;
  });
  useEffect(() => {
    sandpackRef.current = sandpack;
  });

  // Push file changes into Sandpack only when the files array identity changes
  // (debouncedFiles in the parent creates a new array only after the 400ms debounce)
  useEffect(() => {
    const sp = sandpackRef.current;
    for (const f of files) {
      const existing = sp.files[f.path];
      if (!existing || existing.code !== f.content) {
        sp.updateFile(f.path, f.content);
      }
    }
  }, [files]);

  return null;
}

// ── Main component ───────────────────────────────────────────

const LiveCanvas = memo(function LiveCanvas({ files, framework = "vanilla" }: LiveCanvasProps) {
  const [viewport, setViewport] = useState<ViewportPreset>("fluid");
  const [debouncedFiles, setDebouncedFiles] = useState<ProjectFile[]>(files);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce file updates to avoid recompilation on every keystroke
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedFiles(files);
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [files]);

  const sandpackFiles = useMemo(() => toSandpackFiles(debouncedFiles), [debouncedFiles]);

  // Determine if there's an HTML file to render
  const hasHtmlFile = useMemo(
    () => files.some((f) => f.path === "index.html" || f.path.endsWith(".html")),
    [files],
  );

  if (!hasHtmlFile) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-text-secondary">
        <p>No HTML file found. Create an index.html to see a preview.</p>
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
        </div>
        {isConstrained && (
          <span className="text-text-secondary hidden sm:inline">{preset.width}px</span>
        )}
      </div>

      {/* Sandpack preview */}
      <div className="flex-1 flex items-stretch justify-center min-h-0 overflow-auto bg-preview-bg">
        <div
          className={`h-full transition-all duration-200 ${
            isConstrained
              ? "bg-white shadow-2xl my-0 flex-shrink-0"
              : "w-full"
          }`}
          style={
            isConstrained
              ? { width: `${preset.width}px`, maxWidth: "100%", minHeight: "100%" }
              : { width: "100%", minHeight: "100%" }
          }
        >
          <SandpackProvider
            key={framework}
            template={framework === "react" ? "react" : "static"}
            files={sandpackFiles}
            theme="auto"
            options={{
              visibleFiles: [],
              activeFile: framework === "react" ? "/App.jsx" : "/index.html",
              recompileMode: "delayed",
              recompileDelay: 500,
              initMode: "lazy",
            }}
            customSetup={
              framework === "react"
                ? {
                    dependencies: {
                      react: "^18.0.0",
                      "react-dom": "^18.0.0",
                    },
                    entry: "/App.jsx",
                  }
                : undefined
            }
            style={{ height: "100%", width: "100%" }}
          >
            <FileSyncer files={debouncedFiles} />
            <SandpackPreview
              showOpenInCodeSandbox={false}
              showRefreshButton={false}
              className="!h-full !w-full !border-0"
              style={{ height: "100%", width: "100%" }}
            />
          </SandpackProvider>
        </div>
      </div>
    </div>
  );
});

export default LiveCanvas;
