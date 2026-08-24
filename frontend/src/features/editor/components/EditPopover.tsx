"use client";

import { useState, useRef, useEffect, memo, useCallback } from "react";
import type { EditorSelection } from "@/app/lib/types";

interface EditPopoverProps {
  selection: EditorSelection;
  /** Optional anchor element (Monaco editor DOM node) for positioning. */
  anchorRect?: DOMRect | null;
  onClose: () => void;
  /** Called with the user's text instruction to be sent to the AI. */
  onSubmit: (instruction: string) => void;
}

/**
 * A small floating popover that appears near the Monaco editor selection
 * when the user triggers "Edit with AI" from the context menu.
 *
 * The user types their edit instruction and presses Enter to send it to
 * the AI, which then modifies the selected code.
 */
const EditPopover = memo(function EditPopover({
  selection,
  anchorRect,
  onClose,
  onSubmit,
}: EditPopoverProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Close on click outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    // Delay to prevent the context menu click from immediately closing
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClick);
    }, 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [onClose]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const trimmed = value.trim();
        if (!trimmed) return;
        onSubmit(trimmed);
        setValue("");
        onClose();
      }
    },
    [value, onSubmit, onClose],
  );

  // Decide positioning: use anchorRect (from context menu position) or default
  const style: React.CSSProperties = anchorRect
    ? {
        position: "fixed",
        left: anchorRect.left,
        top: anchorRect.bottom + 4,
      }
    : {};

  return (
    <div
      ref={popoverRef}
      style={style}
      className="fixed z-[100] w-80 bg-panel border border-border rounded-xl shadow-2xl animate-scale-in overflow-hidden"
    >
      {/* Header bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-sidebar">
        <svg className="w-3.5 h-3.5 text-accent flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
        <span className="text-xs font-medium text-foreground truncate">
          Edit {selection.filePath}:{selection.startLine}-{selection.endLine}
        </span>
        <button
          onClick={onClose}
          className="ml-auto flex-shrink-0 w-5 h-5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground flex items-center justify-center transition-colors"
          aria-label="Close"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Input area */}
      <div className="p-3">
        <div className="flex items-center gap-2 bg-input border border-border rounded-lg px-3 py-2 focus-within:border-accent/50 focus-within:ring-1 focus-within:ring-accent/20 transition-all">
          <input
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe the edit..."
            className="flex-1 bg-transparent text-sm text-foreground placeholder-text-secondary outline-none"
          />
          <button
            onClick={() => {
              const trimmed = value.trim();
              if (!trimmed) return;
              onSubmit(trimmed);
              setValue("");
              onClose();
            }}
            disabled={!value.trim()}
            className="flex-shrink-0 p-1.5 rounded-md bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            aria-label="Send edit instruction"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
        <p className="text-[10px] text-text-secondary mt-1.5 px-1">
          Press <kbd className="px-1 py-0.5 rounded bg-surface border border-border text-[10px] font-mono">Enter</kbd> to send, <kbd className="px-1 py-0.5 rounded bg-surface border border-border text-[10px] font-mono">Esc</kbd> to cancel
        </p>
      </div>
    </div>
  );
});

export default EditPopover;
