"use client";

import { memo, useCallback } from "react";
import * as Babel from "@babel/standalone";
import type { ProjectFile } from "@/app/lib/types";
import PreviewShell from "@/features/editor/components/PreviewShell";

interface LiveCanvasProps {
  files: ProjectFile[];
  framework?: "vanilla" | "react";
  projectId?: string;
}

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
  const hasHtmlFile = files.some(
    (f) => f.path === "index.html" || f.path === "/index.html" || f.path.endsWith(".html"),
  );

  const buildFn = useCallback((debouncedFiles: ProjectFile[]) => buildPreviewHtml(debouncedFiles), []);

  return (
    <PreviewShell
      files={files}
      onBuildHtml={buildFn}
      noFileMessage="No HTML file found. Create an index.html to see a preview."
      hasRequiredFile={hasHtmlFile}
    />
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
function buildReactPreviewHtml(files: ProjectFile[]): string | { error: string } | null {
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
  const hasJsxFile = files.some(
    (f) => f.path.endsWith(".jsx") || f.path.endsWith(".js"),
  );

  const buildFn = useCallback((debouncedFiles: ProjectFile[]) => {
    try {
      return buildReactPreviewHtml(debouncedFiles);
    } catch (e) {
      return { error: String(e) };
    }
  }, []);

  return (
    <PreviewShell
      files={files}
      onBuildHtml={buildFn}
      noFileMessage="No JSX file found. Create an App.jsx to see a preview."
      hasRequiredFile={hasJsxFile}
    />
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
