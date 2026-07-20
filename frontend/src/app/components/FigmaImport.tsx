"use client";

import { useState } from "react";
import { api } from "../lib/api";
import { useToast } from "./Toast";

interface FigmaImportProps {
  onImportComplete?: (projectId: string) => void;
  variant?: "landing" | "toolbar" | "inline";
}

export default function FigmaImport({ onImportComplete, variant = "landing" }: FigmaImportProps) {
  const [figmaUrl, setFigmaUrl] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [importing, setImporting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const { showToast } = useToast();

  const handleUrlImport = async () => {
    const url = figmaUrl.trim();
    const token = accessToken.trim();
    if (!url) return;
    if (!token) {
      setErrorMsg("A Figma personal access token is required.");
      return;
    }
    setImporting(true);
    setErrorMsg(null);
    try {
      const result = await api.importFigmaUrl(url, token);
      showToast("success", `Imported "${result.project_name}"`);
      onImportComplete?.(result.project_id);
      setFigmaUrl("");
      setAccessToken("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Import failed";
      setErrorMsg(msg);
      // Check if it's a rate limit error with retry info
      const retryAfter = (err as { retryAfter?: number })?.retryAfter;
      if (retryAfter && retryAfter > 0) {
        const mins = Math.floor(retryAfter / 60);
        const secs = retryAfter % 60;
        const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
        showToast("error", `Rate limited — retry in ${timeStr}`);
      } else {
        showToast("error", "Failed to import Figma design");
      }
    } finally {
      setImporting(false);
    }
  };

  // ── Landing page variant ──────────────────────────────────

  if (variant === "landing") {
    return (
      <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-accent" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12h-2v4H7v2h4v4h2v-4h4v-2h-4V8z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-medium text-foreground">Figma Import</h3>
            <p className="text-[11px] text-text-secondary">Paste a Figma URL to generate code</p>
          </div>
        </div>
        <div className="space-y-2">
          <input
            type="text"
            value={figmaUrl}
            onChange={(e) => setFigmaUrl(e.target.value)}
            placeholder="https://www.figma.com/file/ABC123/My-Design"
            className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-text-secondary outline-none focus:border-accent/50"
          />
          <div className="relative">
            <input
              type="password"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              placeholder="Figma personal access token (required)"
              className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-text-secondary outline-none focus:border-accent/50 pr-20"
            />
            <a
              href="https://www.figma.com/settings"
              target="_blank"
              rel="noopener noreferrer"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-accent hover:text-accent-hover underline"
            >
              Get token
            </a>
          </div>
          {errorMsg && (
            <p className="text-xs text-danger">{errorMsg}</p>
          )}
          <button
            onClick={handleUrlImport}
            disabled={!figmaUrl.trim() || !accessToken.trim() || importing}
            className="w-full px-3 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {importing ? (
              <span className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Importing design...
              </span>
            ) : (
              "Import from Figma"
            )}
          </button>
        </div>
      </div>
    );
  }

  // ── Inline variant (compact, for popup menu) ──────────────

  if (variant === "inline") {
    return (
      <div className="p-3 space-y-2">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-accent flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12h-2v4H7v2h4v4h2v-4h4v-2h-4V8z" />
          </svg>
          <span className="text-xs font-semibold text-foreground">Figma Import</span>
        </div>
        <input
          type="text"
          value={figmaUrl}
          onChange={(e) => setFigmaUrl(e.target.value)}
          placeholder="Figma URL"
          className="w-full bg-input border border-border rounded-lg px-2.5 py-1.5 text-xs text-foreground placeholder-text-secondary outline-none focus:border-accent/50"
        />
        <div className="relative">
          <input
            type="password"
            value={accessToken}
            onChange={(e) => setAccessToken(e.target.value)}
            placeholder="Personal access token"
            className="w-full bg-input border border-border rounded-lg px-2.5 py-1.5 text-xs text-foreground placeholder-text-secondary outline-none focus:border-accent/50 pr-16"
          />
          <a
            href="https://www.figma.com/settings"
            target="_blank"
            rel="noopener noreferrer"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-accent hover:text-accent-hover underline"
          >
            Get token
          </a>
        </div>
        {errorMsg && (
          <p className="text-[10px] text-danger">{errorMsg}</p>
        )}
        <button
          onClick={handleUrlImport}
          disabled={!figmaUrl.trim() || !accessToken.trim() || importing}
          className="w-full px-2.5 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {importing ? (
            <span className="flex items-center justify-center gap-1.5">
              <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Importing...
            </span>
          ) : (
            "Import from Figma"
          )}
        </button>
      </div>
    );
  }

  // ── Toolbar variant (icon button opens URL import modal) ─────

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors touch-target"
        title="Import from Figma URL"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12h-2v4H7v2h4v4h2v-4h4v-2h-4V8z" />
        </svg>
      </button>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => { setShowModal(false); setErrorMsg(null); }}>
          <div className="bg-panel border border-border rounded-xl p-5 w-full max-w-md mx-4 shadow-xl max-h-[90dvh] overflow-y-auto" onClick={(e) => e.stopPropagation()} style={{ paddingTop: "env(safe-area-inset-top, 0px)", paddingBottom: "env(safe-area-inset-bottom, 0px)" }}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
                <svg className="w-5 h-5 text-accent" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12h-2v4H7v2h4v4h2v-4h4v-2h-4V8z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">Import from Figma</h3>
                <p className="text-xs text-text-secondary">Paste a Figma URL and your personal access token</p>
              </div>
            </div>
            <div className="space-y-3">
              <input
                type="text"
                value={figmaUrl}
                onChange={(e) => setFigmaUrl(e.target.value)}
                placeholder="https://www.figma.com/file/ABC123/My-Design"
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-text-secondary outline-none focus:border-accent/50"
              />
              <div className="relative">
                <input
                  type="password"
                  value={accessToken}
                  onChange={(e) => setAccessToken(e.target.value)}
                  placeholder="Figma personal access token (required)"
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-text-secondary outline-none focus:border-accent/50 pr-20"
                />
                <a
                  href="https://www.figma.com/settings"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-accent hover:text-accent-hover underline"
                >
                  Get token
                </a>
              </div>
              {errorMsg && (
                <p className="text-xs text-danger">{errorMsg}</p>
              )}
              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => { setShowModal(false); setErrorMsg(null); }}
                  className="flex-1 px-3 py-2 text-sm font-medium rounded-lg border border-border text-foreground hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUrlImport}
                  disabled={!figmaUrl.trim() || !accessToken.trim() || importing}
                  className="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  {importing ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Importing...
                    </span>
                  ) : (
                    "Import"
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
