"use client";

import { useMemo, useState, useEffect, useRef } from "react";
import type { ProjectFile } from "../lib/types";

interface LiveCanvasProps {
  files: ProjectFile[];
}

type ViewportPreset = "fluid" | "desktop" | "tablet" | "mobile";

const VIEWPORT_PRESETS: { key: ViewportPreset; label: string; width: number | null }[] = [
  { key: "fluid", label: "Fluid", width: null },
  { key: "desktop", label: "Desktop", width: 1280 },
  { key: "tablet", label: "Tablet", width: 768 },
  { key: "mobile", label: "Mobile", width: 375 },
];

export default function LiveCanvas({ files }: LiveCanvasProps) {
  const [iframeError, setIframeError] = useState(false);
  const [viewport, setViewport] = useState<ViewportPreset>("fluid");
  const [displayContent, setDisplayContent] = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const htmlContent = useMemo(() => {
    const htmlFile = files.find((f) => f.path === "index.html" || f.path.endsWith(".html"));
    if (!htmlFile) return null;

    // Build maps of filename → content for CSS, JS, and image files
    const cssMap = new Map<string, string>();
    const jsMap = new Map<string, string>();
    const imageMap = new Map<string, string>();
    for (const f of files) {
      if (f.path.endsWith(".css")) {
        const name = f.path.split("/").pop() || f.path;
        cssMap.set(name, f.content);
      } else if (f.path.endsWith(".js")) {
        const name = f.path.split("/").pop() || f.path;
        jsMap.set(name, f.content);
      } else if (f.path.match(/\.(png|jpg|jpeg|gif|webp|svg|ico)$/i)) {
        // Store image files by their full path (e.g., "images/hero.png")
        imageMap.set(f.path, f.content);
      }
    }

    let html = htmlFile.content;

    // Inline CSS: match each <link href="..."> to the correct CSS file by filename
    if (cssMap.size > 0) {
      html = html.replace(
        /<link[^>]*href=["']([^"']*\.css)["'][^>]*\/?>/gi,
        (_match, href: string) => {
          const cssFileName = href.split("/").pop() || href;
          const content = cssMap.get(cssFileName);
          if (content !== undefined) {
            return `<style>\n${content}\n</style>`;
          }
          // If no matching CSS file found, remove the link tag to avoid 404s
          return "";
        },
      );
    }

    // Inline JS: match each <script src="..."> to the correct JS file by filename
    // Handles both regular and type="module" scripts
    if (jsMap.size > 0) {
      html = html.replace(
        /<script[^>]*src=["']([^"']*\.js)["'][^>]*><\/script>/gi,
        (_match, src: string) => {
          const jsFileName = src.split("/").pop() || src;
          const content = jsMap.get(jsFileName);
          if (content !== undefined) {
            return `<script>\n${content}\n</script>`;
          }
          // If no matching project JS file found, preserve the original script tag
          // (it may be a CDN or external script)
          return _match;
        },
      );
    }

    // Inline images: convert <img src="images/..."> to base64 data URIs
    if (imageMap.size > 0) {
      html = html.replace(
        /<img[^>]*src=["']([^"']+)["'][^>]*\/?>/gi,
        (_match, src: string) => {
          // Only inline images that match our project files
          const b64Content = imageMap.get(src);
          if (b64Content) {
            // Determine MIME type from extension
            const ext = src.split(".").pop()?.toLowerCase() || "png";
            const mimeMap: Record<string, string> = {
              png: "image/png",
              jpg: "image/jpeg",
              jpeg: "image/jpeg",
              gif: "image/gif",
              webp: "image/webp",
              svg: "image/svg+xml",
              ico: "image/x-icon",
            };
            const mime = mimeMap[ext] || "image/png";
            return _match.replace(`src="${src}"`, `src="data:${mime};base64,${b64Content}"`);
          }
          // Not a project image — leave the src as-is
          return _match;
        },
      );
    }

    // Inject viewport meta tag for mobile-friendly iframe rendering
    if (!html.includes('name="viewport"') && !html.includes("name='viewport'")) {
      const viewportMeta = '<meta name="viewport" content="width=device-width, initial-scale=1">\n';
      html = html.replace("<head>", `<head>\n${viewportMeta}`);
    }

    // Inject navigation guard: allow hash/anchor links (href="#section")
    // but block external navigation that would redirect the iframe away.
    const navGuard = `
<script>
(function() {
  document.addEventListener('click', function(e) {
    var target = e.target.closest('a');
    if (target && target.href) {
      // Allow hash/anchor links (e.g. href="#home") for SPA navigation
      if (target.href.indexOf('#') !== -1) {
        return;
      }
      // Block all other navigation
      e.preventDefault();
    }
  }, true);
  document.addEventListener('submit', function(e) {
    e.preventDefault();
  }, true);
})();
</script>`;
    html = html.replace("</head>", `${navGuard}\n</head>`);

    return html;
  }, [files]);

  // Debounce srcDoc updates to avoid iframe glitching on rapid keystrokes
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDisplayContent(htmlContent);
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [htmlContent]);

  // Reset iframe error when content changes
  useEffect(() => {
    if (iframeError) {
      const timer = setTimeout(() => setIframeError(false), 0);
      return () => clearTimeout(timer);
    }
  }, [displayContent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Detect iframe load failure: if srcdoc is set but iframe has no content
  // after a short delay, assume rendering failed
  useEffect(() => {
    if (!displayContent) return;
    const timer = setTimeout(() => {
      try {
        const iframe = iframeRef.current;
        if (iframe && iframe.contentDocument) {
          const body = iframe.contentDocument.body;
          if (body && body.innerHTML === "" && displayContent.includes("<body")) {
            setIframeError(true);
          }
        }
      } catch {
        // Cross-origin errors are expected and not a real failure
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, [displayContent]);

  if (!displayContent) {
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
          {VIEWPORT_PRESETS.map((p) => (
            <button
              key={p.key}
              onClick={() => setViewport(p.key)}
              className={`px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                viewport === p.key
                  ? "bg-accent text-white"
                  : "text-text-secondary hover:text-foreground hover:bg-surface"
              }`}
              title={`${p.label}${p.width ? ` — ${p.width}px` : ""}`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {iframeError && (
          <span className="text-danger">Failed to render preview</span>
        )}
        {isConstrained && (
          <span className="text-text-secondary hidden sm:inline">{preset.width}px</span>
        )}
      </div>
      {/* Iframe container — constrained width when a device preset is active */}
      <div className="flex-1 flex items-start justify-center min-h-0 overflow-auto bg-preview-bg">
        <div
          className={`h-full transition-all duration-200 ${
            isConstrained
              ? "bg-white shadow-2xl my-0 flex-shrink-0"
              : "w-full"
          }`}
          style={
            isConstrained
              ? { width: `${preset.width}px`, maxWidth: "100%" }
              : undefined
          }
        >
          <iframe
            ref={iframeRef}
            srcDoc={displayContent}
            sandbox="allow-scripts allow-same-origin"
            title="Live Preview"
            className="w-full h-full border-0"
          />
        </div>
      </div>
    </div>
  );
}
