"use client";

import { useState, useRef, useEffect, memo } from "react";
import { Spinner } from "@/components/ui/Spinner";
import FigmaImport from "@/features/editor/components/FigmaImport";
import type { FigmaImportHandle } from "@/features/editor/components/FigmaImport";
import DesignUpload from "@/features/editor/components/DesignUpload";
import type { DesignUploadHandle } from "@/features/editor/components/DesignUpload";
import TemplateGallery from "@/features/projects/components/TemplateGallery";
import type { TemplateGalleryHandle } from "@/features/projects/components/TemplateGallery";

interface LandingPageProps {
  generating: boolean;
  onSendPrompt: (prompt: string) => void;
  framework: "vanilla" | "react";
  onFrameworkChange: (framework: "vanilla" | "react") => void;
  onFigmaImportComplete?: (projectId: string) => void;
  onDesignUploadComplete?: (projectId: string) => void;
  onCreateFromTemplate?: (templateId: string) => void;
}

/**
 * Centered chat landing page — shown when no project is selected.
 */
const LandingPage = memo(function LandingPage({
  generating,
  onSendPrompt,
  framework,
  onFrameworkChange,
  onFigmaImportComplete,
  onDesignUploadComplete,
  onCreateFromTemplate,
}: LandingPageProps) {
  const [promptValue, setPromptValue] = useState("");
  const [showLandingMenu, setShowLandingMenu] = useState(false);
  const promptTextareaRef = useRef<HTMLTextAreaElement>(null);
  const landingMenuRef = useRef<HTMLDivElement>(null);
  const figmaRef = useRef<FigmaImportHandle>(null);
  const designRef = useRef<DesignUploadHandle>(null);
  const templateRef = useRef<TemplateGalleryHandle>(null);

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

  const handleSend = () => {
    const trimmed = promptValue.trim();
    if (!trimmed || generating) return;
    onSendPrompt(trimmed);
    setPromptValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

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
        <div className="w-full flex items-center gap-2 bg-input border border-border rounded-xl px-3 py-2 focus-within:border-accent/50 focus-within:ring-1 focus-within:ring-accent/20 transition-all">
          <div className="relative" ref={landingMenuRef}>
            <button
              onClick={() => setShowLandingMenu((prev) => !prev)}
              className="flex-shrink-0 w-7 h-7 rounded-full bg-accent/10 hover:bg-accent/20 text-accent hover:text-accent-hover flex items-center justify-center transition-colors touch-target"
              title="Import or upload"
              aria-label="Import or upload"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
            </button>

            {showLandingMenu && (
              <div className="absolute bottom-full left-0 mb-2 w-56 bg-panel border border-border rounded-xl shadow-xl overflow-hidden z-50 animate-scale-in" role="menu">
                <div className="p-3 space-y-1">
                  <p className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider px-1 pb-1">Import</p>
                  <button
                    onClick={() => { setShowLandingMenu(false); templateRef.current?.open(); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-surface transition-colors text-left"
                    role="menuitem"
                  >
                    <svg className="w-4 h-4 text-accent flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h7" />
                    </svg>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-foreground">From Template</div>
                      <div className="text-[10px] text-text-secondary truncate">Start with a pre-built starter</div>
                    </div>
                  </button>
                  <hr className="border-border my-1" />
                  <button
                    onClick={() => { setShowLandingMenu(false); figmaRef.current?.open(); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-surface transition-colors text-left"
                    role="menuitem"
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
                    onClick={() => { setShowLandingMenu(false); designRef.current?.open(); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-surface transition-colors text-left"
                    role="menuitem"
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
            onKeyDown={handleKeyDown}
            placeholder="e.g. Build a landing page with a hero section..."
            disabled={generating}
            className="flex-1 bg-transparent text-sm text-foreground placeholder-text-secondary resize-none outline-none focus-visible:outline-none max-h-[200px]"
          />
          <button
            onClick={handleSend}
            disabled={!promptValue.trim() || generating}
            aria-label="Send prompt"
            className="flex-shrink-0 p-1.5 rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors touch-target"
          >
            {generating ? (
              <Spinner className="w-4 h-4" color="white" />
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>

        {/* Framework toggle on landing page */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onFrameworkChange("vanilla")}
            className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
              framework === "vanilla"
                ? "bg-accent text-white"
                : "bg-surface text-text-secondary hover:text-foreground border border-border"
            }`}
          >
            Vanilla
          </button>
          <button
            onClick={() => onFrameworkChange("react")}
            className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
              framework === "react"
                ? "bg-accent text-white"
                : "bg-surface text-text-secondary hover:text-foreground border border-border"
            }`}
          >
            React
          </button>
        </div>

        {/* Browse Templates button */}
        <button
          onClick={() => templateRef.current?.open()}
          className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h7" />
          </svg>
          Browse Templates
        </button>

        <p className="text-xs text-text-secondary text-center">
          AI-generated code may not always be perfect. Review and test before using.
        </p>
      </div>

      {/* Imperative modals for landing page — always rendered but invisible */}
      <TemplateGallery ref={templateRef} framework={framework} onSelectTemplate={(id) => onCreateFromTemplate?.(id)} />
      <FigmaImport ref={figmaRef} variant="modal-only" onImportComplete={onFigmaImportComplete} />
      <DesignUpload ref={designRef} projectId="" variant="modal-only" onUploadComplete={onDesignUploadComplete} />
    </div>
  );
});

export default LandingPage;
