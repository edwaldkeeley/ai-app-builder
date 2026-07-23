"use client";

import Modal from "./Modal";

interface ShortcutsModalProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS = [
  { keys: "Ctrl+S", label: "Save all files" },
  { keys: "Ctrl+Tab / Ctrl+PageDown", label: "Cycle files forward" },
  { keys: "Ctrl+PageUp", label: "Cycle files backward" },
  { keys: "Ctrl+B", label: "Toggle sidebar" },
  { keys: "Ctrl+Shift+P", label: "Cycle view mode" },
  { keys: "Ctrl+Shift+N", label: "New project" },
  { keys: "Escape", label: "Close panels / cancel" },
];

export default function ShortcutsModal({ open, onClose }: ShortcutsModalProps) {
  return (
    <Modal open={open} onClose={onClose}>
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
            <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">Keyboard Shortcuts</h3>
            <p className="text-xs text-text-secondary">Quick reference for available shortcuts</p>
          </div>
        </div>
        <div className="space-y-1">
          {SHORTCUTS.map(({ keys, label }) => (
            <div key={keys} className="flex items-center justify-between py-1.5 px-1 rounded-lg hover:bg-surface transition-colors">
              <span className="text-xs text-foreground">{label}</span>
              <kbd className="px-2 py-0.5 text-[10px] font-mono font-medium bg-surface border border-border rounded text-text-secondary">
                {keys}
              </kbd>
            </div>
          ))}
        </div>
        <div className="pt-2">
          <button
            onClick={onClose}
            className="w-full px-3 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
          >
            Got it
          </button>
        </div>
      </div>
    </Modal>
  );
}
