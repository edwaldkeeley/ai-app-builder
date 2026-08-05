"use client";

import { memo, useMemo, useState, useEffect, useRef } from "react";
import * as Babel from "@babel/standalone";
import type { ProjectFile } from "@/app/lib/types";

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
  const htmlFile = files.find(
    (f) => f.path === "index.html" || f.path === "/index.html" || f.path.endsWith(".html"),
  );
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
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [files]);

  const htmlContent = useMemo(() => buildPreviewHtml(debouncedFiles), [debouncedFiles]);

  // Create blob URL from htmlContent and revoke old ones
  useEffect(() => {
    if (!htmlContent) return;
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

// ── React: transpile JSX with @babel/standalone and render via iframe ──

/**
 * Transpile a JSX/JS file using @babel/standalone.
 * Returns the compiled code, or the original code if it's not JSX.
 */
function transpileJsx(code: string, filename: string): string {
  // Only transpile .jsx files (and .js files that might contain JSX)
  if (!filename.endsWith(".jsx") && !filename.endsWith(".js")) {
    return code;
  }
  try {
    const result = Babel.transform(code, {
      presets: [
        ["react", { runtime: "classic" }],
      ],
      filename,
      retainLines: true,
      compact: false,
    });
    return result.code ?? code;
  } catch {
    // If transpilation fails, return the original code
    return code;
  }
}

/**
 * Build a self-contained HTML page for React projects.
 * Includes React/ReactDOM from CDN, inlined CSS, and transpiled JSX.
 */
function buildReactPreviewHtml(files: ProjectFile[]): string | null {
  // Find JSX/JS files
  const jsxFiles = files.filter(
    (f) => f.path.endsWith(".jsx") || f.path.endsWith(".js"),
  );
  if (jsxFiles.length === 0) return null;

  // Find CSS files
  const cssFiles = files.filter((f) => f.path.endsWith(".css"));

  // Determine entry point: App.jsx > index.jsx > first .jsx > first .js
  const entry =
    jsxFiles.find((f) => f.path === "App.jsx" || f.path === "/App.jsx") ??
    jsxFiles.find((f) => f.path === "index.jsx" || f.path === "/index.jsx") ??
    jsxFiles.find((f) => f.path.endsWith(".jsx")) ??
    jsxFiles[0];

  // Transpile all JSX/JS files
  const transpiled = new Map<string, string>();
  for (const f of jsxFiles) {
    const name = f.path.startsWith("/") ? f.path.slice(1) : f.path;
    try {
      const code = transpileJsx(f.content, name);
      transpiled.set(name, code);
    } catch (e) {
      transpiled.set(name, `/* Error transpiling ${name}: ${e} */\n${f.content}`);
    }
  }

  // Build inline CSS
  const inlineCss = cssFiles.map((f) => f.content).join("\n");

  // Build script tags for each transpiled file
  const scriptTags: string[] = [];
  for (const [name, code] of transpiled) {
    // Skip the entry point — we'll handle it separately
    const entryName = entry.path.startsWith("/") ? entry.path.slice(1) : entry.path;
    if (name === entryName) continue;
    scriptTags.push(`<script>\n${code}\n</script>`);
  }

  // Build the entry point script — wrap to render into #root
  const entryName = entry.path.startsWith("/") ? entry.path.slice(1) : entry.path;
  const entryCode = transpiled.get(entryName) ?? entry.content;

  // Try to detect the component name from the entry file
  // We use React.createElement with the first exported/defined component
  const renderScript = `
(function() {
  ${entryCode}

  // Find the main component (last defined function or variable)
  var root = document.getElementById('root');
  if (root) {
    // Try to find the component by looking for common patterns
    var component = null;
    if (typeof App !== 'undefined') component = App;
    else if (typeof Index !== 'undefined') component = Index;
    else if (typeof Home !== 'undefined') component = Home;
    else if (typeof Page !== 'undefined') component = Page;

    if (component) {
      var reactRoot = ReactDOM.createRoot(root);
      reactRoot.render(React.createElement(component));
    } else {
      // Fallback: try to render whatever was exported
      root.innerHTML = '<div style="color:red;padding:20px">Error: No React component found. Make sure to define a component (e.g., function App() { ... }).</div>';
    }
  }
})();
`;

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
  ${inlineCss ? `<style>\n${inlineCss}\n</style>` : ""}
</head>
<body>
  <div id="root"></div>
  ${scriptTags.join("\n  ")}
  <script>\n${renderScript}\n</script>
</body>
</html>`;

  return html;
}

function ReactPreview({ files }: { files: ProjectFile[] }) {
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
  }, [files]);

  // Build HTML from debounced files
  const htmlContent = useMemo(() => {
    try {
      return buildReactPreviewHtml(debouncedFiles);
    } catch (e) {
      return { error: String(e) };
    }
  }, [debouncedFiles]);

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

  const hasJsxFile = files.some(
    (f) => f.path.endsWith(".jsx") || f.path.endsWith(".js"),
  );

  if (!hasJsxFile) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-text-secondary">
        <p>No JSX file found. Create an App.jsx to see a preview.</p>
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
            title="React Preview"
            sandbox="allow-forms allow-modals allow-popups allow-same-origin allow-scripts"
            className="w-full h-full border-0"
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      </div>
    </div>
  );
}

// ── Main component ──

const LiveCanvas = memo(function LiveCanvas({
  files,
  framework = "vanilla",
}: LiveCanvasProps) {
  if (framework === "react") {
    return <ReactPreview files={files} />;
  }
  return <VanillaPreview files={files} />;
});

export default LiveCanvas;
