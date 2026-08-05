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
  onCycleFiles?: () => void;
  onCycleFilesBackward?: () => void;
}

/**
 * Global keyboard shortcuts hook.
 * Registers a single keydown listener that reads handlers from a ref,
 * avoiding re-registration when handlers change.
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
  const handlersRef = useRef(handlers);

  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const h = handlersRef.current;
      const isMod = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();

      // Ctrl+S / Cmd+S — Save
      if (isMod && key === "s" && h.onSave) {
        e.preventDefault();
        h.onSave();
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

      // Ctrl+Shift+P — Toggle view mode
      if (isMod && e.shiftKey && key === "p") {
        e.preventDefault();
        h.onToggleViewMode?.();
        return;
      }

      // Ctrl+Tab / Cmd+Tab — Cycle files forward
      if ((e.ctrlKey || e.metaKey) && key === "tab") {
        e.preventDefault();
        e.stopPropagation();
        h.onCycleFiles?.();
        return;
      }

      // Ctrl+PageDown / Cmd+PageDown — Cycle forward
      if ((e.ctrlKey || e.metaKey) && key === "pagedown") {
        e.preventDefault();
        h.onCycleFiles?.();
        return;
      }

      // Ctrl+PageUp / Cmd+PageUp — Cycle backward
      if ((e.ctrlKey || e.metaKey) && key === "pageup") {
        e.preventDefault();
        h.onCycleFilesBackward?.();
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
  }, []);
}
