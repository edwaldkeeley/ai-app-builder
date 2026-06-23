"use client";

import { useMemo, useState } from "react";
import type { ProjectFile } from "../lib/types";

interface LiveCanvasProps {
  files: ProjectFile[];
}

export default function LiveCanvas({ files }: LiveCanvasProps) {
  const [iframeError, setIframeError] = useState(false);

  const htmlContent = useMemo(() => {
    const htmlFile = files.find((f) => f.path === "index.html" || f.path.endsWith(".html"));
    const cssFile = files.find((f) => f.path === "style.css" || f.path.endsWith(".css"));
    const jsFile = files.find((f) => f.path === "script.js" || f.path.endsWith(".js"));

    if (!htmlFile) return null;

    let html = htmlFile.content;

    // Inline CSS if linked via <link>
    if (cssFile) {
      html = html.replace(
        /<link[^>]*href=["']([^"']*\.css)["'][^>]*\/?>/gi,
        () => `<style>\n${cssFile.content}\n</style>`,
      );
    }

    // Inline JS if linked via <script src>
    if (jsFile) {
      html = html.replace(
        /<script[^>]*src=["']([^"']*\.js)["'][^>]*><\/script>/gi,
        () => `<script>\n${jsFile.content}\n</script>`,
      );
    }

    return html;
  }, [files]);

  if (!htmlContent) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-text-secondary">
        <p>No HTML file found. Create an index.html to see a preview.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-white">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-sidebar border-b border-border text-xs text-text-secondary">
        <span>Preview</span>
        {iframeError && (
          <span className="text-danger">Failed to render preview</span>
        )}
      </div>
      {/* Iframe */}
      <div className="flex-1 min-h-0">
        <iframe
          key={htmlContent.slice(0, 100)}
          srcDoc={htmlContent}
          sandbox="allow-scripts"
          title="Live Preview"
          className="w-full h-full border-0"
          onError={() => setIframeError(true)}
        />
      </div>
    </div>
  );
}
