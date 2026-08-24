"use client";

import type { EditorSelection } from "@/app/lib/types";

/**
 * Module-level selection store for AI editing.
 *
 * Bridges the Monaco editor (where selections originate) with the chat system
 * (where they're used for context injection) without prop drilling through
 * multiple component layers.
 *
 * Usage:
 *   EditorPane → setEditorSelection(sel) on cursor change
 *   useChat    → getEditorSelection() to read when sending a prompt
 *   ChatPanel  → useSyncExternalStore(subscribe, get) for reactive badge
 */

let _selection: EditorSelection | null = null;
const listeners = new Set<() => void>();

export function getEditorSelection(): EditorSelection | null {
  return _selection;
}

export function setEditorSelection(sel: EditorSelection | null): void {
  _selection = sel;
  listeners.forEach((fn) => fn());
}

export function subscribeToEditorSelection(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
