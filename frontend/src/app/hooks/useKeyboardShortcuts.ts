"use client";

import { useEffect } from "react";

export interface ShortcutHandlers {
  onSave?: () => void;
  onEscape?: () => void;
  onToggleSidebar?: () => void;
  onToggleExplorer?: () => void;
  onToggleViewMode?: () => void;
  onNewProject?: () => void;
  onFocusPrompt?: () => void;
  onCycleFiles?: () => void;
  onCycleFilesBackward?: () => void;
}

/**
 * Global keyboard shortcuts hook.
 * Registers keydown listeners on the document and calls the provided handlers.
 * Re-registers the listener whenever handlers change.
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMod = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();

      // Ctrl+S / Cmd+S — Save
      if (isMod && key === "s" && handlers.onSave) {
        e.preventDefault();
        handlers.onSave();
        return;
      }

      // Escape — Close panels / cancel
      if (e.key === "Escape") {
        handlers.onEscape?.();
        return;
      }

      // Ctrl+B / Cmd+B — Toggle sidebar
      if (isMod && key === "b") {
        e.preventDefault();
        handlers.onToggleSidebar?.();
        return;
      }

      // Ctrl+Shift+E — Toggle file explorer
      if (isMod && e.shiftKey && key === "e") {
        e.preventDefault();
        handlers.onToggleExplorer?.();
        return;
      }

      // Ctrl+Shift+P — Toggle view mode
      if (isMod && e.shiftKey && key === "p") {
        e.preventDefault();
        handlers.onToggleViewMode?.();
        return;
      }

      // Ctrl+Tab / Cmd+Tab — Cycle files forward
      if ((e.ctrlKey || e.metaKey) && key === "tab") {
        e.preventDefault();
        e.stopPropagation();
        handlers.onCycleFiles?.();
        return;
      }

      // Ctrl+PageDown / Cmd+PageDown — Cycle forward
      if ((e.ctrlKey || e.metaKey) && key === "pagedown") {
        e.preventDefault();
        handlers.onCycleFiles?.();
        return;
      }

      // Ctrl+PageUp / Cmd+PageUp — Cycle backward
      if ((e.ctrlKey || e.metaKey) && key === "pageup") {
        e.preventDefault();
        handlers.onCycleFilesBackward?.();
        return;
      }

      // Ctrl+Shift+N — New project
      if (isMod && e.shiftKey && key === "n") {
        e.preventDefault();
        handlers.onNewProject?.();
        return;
      }

      // Ctrl+Shift+F — Focus prompt input
      if (isMod && e.shiftKey && key === "f") {
        e.preventDefault();
        handlers.onFocusPrompt?.();
        return;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handlers]);
}
