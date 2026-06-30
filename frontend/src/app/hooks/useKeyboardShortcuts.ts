"use client";

import { useEffect, useRef } from "react";

export interface ShortcutHandlers {
  onSave?: () => void;
  onEscape?: () => void;
  onToggleSidebar?: () => void;
  onToggleExplorer?: () => void;
  onToggleViewMode?: () => void;
  onNewProject?: () => void;
  onFocusPrompt?: () => void;
}

/**
 * Global keyboard shortcuts hook.
 * Registers keydown listeners on the document and calls the provided handlers.
 * Uses a ref to avoid re-registering the listener on every render.
 * All handlers are optional — only register the ones you need.
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
  const handlersRef = useRef(handlers);

  // Sync ref with latest handlers (in effect, not during render)
  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const h = handlersRef.current;
      const isMod = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();

      // Ctrl+S / Cmd+S — Save
      if (isMod && key === "s") {
        e.preventDefault();
        h.onSave?.();
        return;
      }

      // Escape — Close panels / cancel
      if (e.key === "Escape") {
        h.onEscape?.();
        return;
      }

      // Ctrl+B / Cmd+B — Toggle sidebar
      if (isMod && key === "b") {
        e.preventDefault();
        h.onToggleSidebar?.();
        return;
      }

      // Ctrl+Shift+E — Toggle file explorer
      if (isMod && e.shiftKey && key === "e") {
        e.preventDefault();
        h.onToggleExplorer?.();
        return;
      }

      // Ctrl+Shift+P — Cycle view mode (Preview → Code → Split)
      if (isMod && e.shiftKey && key === "p") {
        e.preventDefault();
        h.onToggleViewMode?.();
        return;
      }

      // Ctrl+Shift+N — New project
      if (isMod && e.shiftKey && key === "n") {
        e.preventDefault();
        h.onNewProject?.();
        return;
      }

      // Ctrl+Shift+F — Focus prompt input
      if (isMod && e.shiftKey && key === "f") {
        e.preventDefault();
        h.onFocusPrompt?.();
        return;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []); // Empty deps — handlers read from ref, so no re-registration needed
}
