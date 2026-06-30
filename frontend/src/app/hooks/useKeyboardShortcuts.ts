"use client";

import { useEffect } from "react";

interface ShortcutHandlers {
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
 * All handlers are optional — only register the ones you need.
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMod = e.ctrlKey || e.metaKey;

      // Ctrl+S / Cmd+S — Save
      if (isMod && e.key === "s") {
        e.preventDefault();
        handlers.onSave?.();
        return;
      }

      // Escape — Close panels / cancel
      if (e.key === "Escape") {
        handlers.onEscape?.();
        return;
      }

      // Ctrl+B / Cmd+B — Toggle sidebar
      if (isMod && e.key === "b") {
        e.preventDefault();
        handlers.onToggleSidebar?.();
        return;
      }

      // Ctrl+Shift+E — Toggle file explorer
      if (isMod && e.shiftKey && e.key === "E") {
        e.preventDefault();
        handlers.onToggleExplorer?.();
        return;
      }

      // Ctrl+Shift+P — Cycle view mode (Preview → Code → Split)
      if (isMod && e.shiftKey && e.key === "P") {
        e.preventDefault();
        handlers.onToggleViewMode?.();
        return;
      }

      // Ctrl+Shift+N — New project
      if (isMod && e.shiftKey && e.key === "N") {
        e.preventDefault();
        handlers.onNewProject?.();
        return;
      }

      // Ctrl+Shift+F — Focus prompt input
      if (isMod && e.shiftKey && e.key === "F") {
        e.preventDefault();
        handlers.onFocusPrompt?.();
        return;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handlers]);
}
