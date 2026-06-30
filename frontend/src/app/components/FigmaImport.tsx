"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import type { FigmaFile } from "../lib/types";
import { useToast } from "./Toast";

type FigmaState = "idle" | "connecting" | "connected" | "importing" | "error";

interface FigmaImportProps {
  onImportComplete?: (projectId: string) => void;
  variant?: "landing" | "toolbar";
}

export default function FigmaImport({ onImportComplete, variant = "landing" }: FigmaImportProps) {
  const [state, setState] = useState<FigmaState>("idle");
  const [figmaFiles, setFigmaFiles] = useState<FigmaFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const { showToast } = useToast();

  const loadFigmaFiles = useCallback(async () => {
    try {
      const result = await api.listFigmaFiles();
      setFigmaFiles(result.files);
    } catch {
      showToast("error", "Failed to load Figma files");
    }
  }, [showToast]);

  // Listen for OAuth callback from popup window
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Security: only accept messages from our own origin
      if (event.origin !== window.origin) return;
      if (event.data?.type !== "figma-oauth") return;

      if (event.data.status === "connected") {
        setState("connected");
        showToast("success", "Connected to Figma");
        loadFigmaFiles();
      } else if (event.data.status === "error") {
        const msg = event.data.message || "Authentication failed";
        setState("error");
        setErrorMsg(msg);
        showToast("error", "Figma connection failed");
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [showToast, loadFigmaFiles]);

  // Check connection status on mount
  useEffect(() => {
    api.getFigmaStatus().then((status) => {
      if (status.connected) {
        setState("connected");
        loadFigmaFiles();
      }
    }).catch(() => {
      // Not connected — stay in idle state
    });
  }, [loadFigmaFiles]);

  const handleConnect = async () => {
    setState("connecting");
    setErrorMsg(null);
    try {
      const { url } = await api.getFigmaAuthUrl();
      // Open OAuth popup
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      window.open(
        url,
        "figma-oauth",
        `width=${width},height=${height},left=${left},top=${top},popup=1`,
      );
      // Connection result comes via postMessage
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start Figma authentication";
      setState("error");
      setErrorMsg(msg);
      showToast("error", msg);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) return;
    setState("importing");
    setErrorMsg(null);
    try {
      const result = await api.importFigmaFile(selectedFile);
      showToast("success", `Imported "${result.project_name}"`);
      onImportComplete?.(result.project_id);
      setState("connected");
    } catch (err) {
      setState("error");
      const msg = err instanceof Error ? err.message : "Import failed";
      setErrorMsg(msg);
      showToast("error", "Failed to import Figma design");
    }
  };

  const handleRefresh = () => {
    loadFigmaFiles();
  };

  // ── Landing page variant ──────────────────────────────────

  if (variant === "landing") {
    return (
      <div className="w-full">
        {state === "idle" && (
          <button
            onClick={handleConnect}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border border-border bg-surface text-foreground hover:bg-sidebar hover:border-accent/30 transition-all"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12h-2v4H7v2h4v4h2v-4h4v-2h-4V8z" />
            </svg>
            Import from Figma
          </button>
        )}

        {state === "connecting" && (
          <div className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm text-text-secondary">
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span>Connecting to Figma...</span>
          </div>
        )}

        {state === "connected" && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-green-500">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              <span>Connected to Figma</span>
              <button
                onClick={handleRefresh}
                className="ml-auto p-0.5 rounded hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
                title="Refresh files"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>
            <select
              value={selectedFile}
              onChange={(e) => setSelectedFile(e.target.value)}
              className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-accent/50"
            >
              <option value="">Select a Figma file...</option>
              {figmaFiles.map((f) => (
                <option key={f.key} value={f.key}>
                  {f.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleImport}
              disabled={!selectedFile}
              className="w-full px-3 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Import Design
            </button>
          </div>
        )}

        {state === "importing" && (
          <div className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm text-text-secondary">
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span>Importing design...</span>
          </div>
        )}

        {state === "error" && (
          <div className="space-y-2">
            <p className="text-xs text-danger">{errorMsg || "Something went wrong"}</p>
            <button
              onClick={() => setState("idle")}
              className="w-full px-3 py-2 text-sm font-medium rounded-lg border border-border text-foreground hover:bg-surface transition-colors"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── Toolbar variant (icon button in project name bar) ─────

  return (
    <div className="relative">
      {state === "idle" || state === "error" ? (
        <button
          onClick={handleConnect}
          className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
          title="Import from Figma"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12h-2v4H7v2h4v4h2v-4h4v-2h-4V8z" />
          </svg>
        </button>
      ) : state === "connecting" ? (
        <div className="p-1.5">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <button
          onClick={handleImport}
          disabled={!selectedFile || state === "importing"}
          className="p-1.5 rounded-md hover:bg-surface text-green-500 hover:text-green-400 transition-colors"
          title="Import from Figma"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12h-2v4H7v2h4v4h2v-4h4v-2h-4V8z" />
          </svg>
        </button>
      )}
    </div>
  );
}
