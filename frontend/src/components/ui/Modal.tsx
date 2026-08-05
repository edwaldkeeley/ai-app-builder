"use client";
import { type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

/**
 * Shared modal wrapper — fixed overlay with centered panel, click-outside-to-close,
 * safe-area padding, and consistent border/shadow/rounded styling.
 */
export default function Modal({ open, onClose, children }: ModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-panel border border-border rounded-xl shadow-xl w-full max-w-md max-h-[90dvh] overflow-y-auto animate-scale-in"
        onClick={(e) => e.stopPropagation()}
        style={{
          paddingTop: "calc(20px + env(safe-area-inset-top, 0px))",
          paddingBottom: "calc(20px + env(safe-area-inset-bottom, 0px))",
          paddingLeft: "20px",
          paddingRight: "20px",
        }}
      >
        {children}
      </div>
    </div>
  );
}
