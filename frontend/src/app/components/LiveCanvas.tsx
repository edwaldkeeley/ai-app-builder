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
  projectId?: string;
}

type ViewportPreset = "fluid" | "desktop" | "tablet" | "mobile";

const VIEWPORT_PRESETS: { key: ViewportPreset; label: string; width: number | null }[] = [
  { key: "fluid", label: "Fluid", width: null },
  { key: "desktop", label: "Desktop", width: 1280 },
  { key: "tablet", label: "Tablet", width: 768 },
  { key: "mobile", label: "Mobile", width: 375 },
];

// ── Vanilla: inline CSS/JS into HTML and render via srcdoc iframe ──

function buildPreviewHtml(files: ProjectFile[]): string | null {
  const htmlFile = files.find((f) => f.path === "index.html" || f.path === "/index.html" || f.path.endsWith(".html"));
  if (!htmlFile) return null;

  const cssMap = new Map<string, string>();
  const jsMap = new Map<string, string>();
  for (const f of files) {
    const name = f.path.split("/").pop() || f.path;
    if (f.path.endsWith(".css")) cssMap.set(name, f.content);
    else if (f.path.endsWith(".js")) jsMap.set(name, f.content);
  }

  let html = htmlFile.content;

  // Inline CSS
  if (cssMap.size > 0) {
    html = html.replace(
      /<link[^>]*href=["']([^"']*\.css)["'][^>]*\/?>/gi,
      (_match, href: string) => {
        const name = href.split("/").pop() || href;
        const content = cssMap.get(name);
        return content !== undefined ? `<style>\n${content}\n</style>` : "";
      },
    );
  }

  // Inline JS
  if (jsMap.size > 0) {
    html = html.replace(
      /<script[^>]*src=["']([^"']*\.js)["'][^>]*><\/script>/gi,
      (_match, src: string) => {
        const name = src.split("/").pop() || src;
        const content = jsMap.get(name);
        if (content !== undefined) {
          return `<script>\n${content}\n</script>`;
        }
        return _match; // preserve external/CDN scripts
      },
    );
  }

  return html;
}

function VanillaPreview({ files }: { files: ProjectFile[] }) {
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
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [files]);

  const htmlContent = useMemo(() => buildPreviewHtml(debouncedFiles), [debouncedFiles]);

  // Create blob URL from htmlContent and revoke old ones
  useEffect(() => {
    if (!htmlContent) return;
    // Revoke previous blob URL
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
    }
    const blob = new Blob([htmlContent], { type: "text/html" });
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
  }, [htmlContent]);

  const hasHtmlFile = files.some(
    (f) => f.path === "index.html" || f.path === "/index.html" || f.path.endsWith(".html"),
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
}

// ── React: Sandpack-based preview (needs JSX compilation) ──────

function toSandpackFiles(files: ProjectFile[]): Record<string, { code: string }> {
  const result: Record<string, { code: string }> = {};
  for (const f of files) {
    const sandpackPath = f.path.startsWith("/") ? f.path : `/${f.path}`;
    result[sandpackPath] = { code: f.content };
  }
  return result;
}

function FileSyncer({ files }: { files: ProjectFile[] }) {
  const { sandpack } = useSandpack();
  const filesRef = useRef(files);
  const sandpackRef = useRef(sandpack);

  useEffect(() => { filesRef.current = files; });
  useEffect(() => { sandpackRef.current = sandpack; });

  useEffect(() => {
    const sp = sandpackRef.current;
    for (const f of files) {
      const sandpackPath = f.path.startsWith("/") ? f.path : `/${f.path}`;
      const existing = sp.files[sandpackPath];
      if (!existing || existing.code !== f.content) {
        sp.updateFile(sandpackPath, f.content);
      }
    }
  }, [files]);

  return null;
}

const ReactPreview = memo(function ReactPreview({
  files,
  projectId,
}: {
  files: ProjectFile[];
  projectId?: string;
}) {
  const [viewport, setViewport] = useState<ViewportPreset>("fluid");
  const [debouncedFiles, setDebouncedFiles] = useState<ProjectFile[]>(files);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const isInitialLoad = debouncedFiles.length === 0 && files.length > 0;
    debounceRef.current = setTimeout(() => {
      setDebouncedFiles(files);
    }, isInitialLoad ? 0 : 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [files]);

  const sandpackFiles = useMemo(() => toSandpackFiles(debouncedFiles), [debouncedFiles]);

  const hasHtmlFile = files.some(
    (f) => f.path === "index.html" || f.path === "/index.html" || f.path.endsWith(".html"),
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
            isConstrained ? "bg-white shadow-2xl my-0 flex-shrink-0" : "w-full"
          }`}
          style={
            isConstrained
              ? { width: `${preset.width}px`, maxWidth: "100%", minHeight: "100%" }
              : { width: "100%", minHeight: "100%" }
          }
        >
          <SandpackProvider
            key={projectId ?? "react"}
            template="react"
            files={sandpackFiles}
            theme="auto"
            options={{
              visibleFiles: [],
              activeFile: "/App.jsx",
              recompileMode: "delayed",
              recompileDelay: 500,
            }}
            customSetup={{
              dependencies: {
                react: "^18.0.0",
                "react-dom": "^18.0.0",
              },
              entry: "/App.jsx",
            }}
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

// ── Main component ───────────────────────────────────────────

const LiveCanvas = memo(function LiveCanvas({ files, framework = "vanilla", projectId }: LiveCanvasProps) {
  if (framework === "react") {
    return <ReactPreview files={files} projectId={projectId} />;
  }
  return <VanillaPreview files={files} />;
});

export default LiveCanvas;
