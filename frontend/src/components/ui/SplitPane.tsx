"use client";

import { useState, useRef, useEffect, useCallback, type ReactNode } from "react";

interface SplitPaneProps {
  left: ReactNode;
  right: ReactNode;
  /** Initial ratio (0-1). Default 0.5. */
  defaultRatio?: number;
  /** Minimum ratio. Default 0.2. */
  minRatio?: number;
  /** Maximum ratio. Default 0.8. */
  maxRatio?: number;
}

/**
 * A resizable split pane with a draggable divider.
 * The left pane width is controlled by `ratio` (0-1).
 * Supports mouse drag to resize.
 */
export default function SplitPane({
  left,
  right,
  defaultRatio = 0.5,
  minRatio = 0.2,
  maxRatio = 0.8,
}: SplitPaneProps) {
  const [ratio, setRatio] = useState(defaultRatio);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const newRatio = (e.clientX - rect.left) / rect.width;
      setRatio(Math.max(minRatio, Math.min(maxRatio, newRatio)));
    };
    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [minRatio, maxRatio]);

  return (
    <div ref={containerRef} className="flex-1 flex min-h-0">
      <div
        className="flex flex-col min-w-0 overflow-hidden"
        style={{ width: `${ratio * 100}%` }}
      >
        {left}
      </div>
      {/* Draggable divider */}
      <div
        onMouseDown={handleMouseDown}
        className="w-1.5 bg-border hover:bg-accent/50 active:bg-accent cursor-col-resize flex-shrink-0 transition-colors relative z-10"
      >
        <div className="absolute inset-y-0 -left-1 -right-1" />
      </div>
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {right}
      </div>
    </div>
  );
}
