"use client";

/**
 * Reusable skeleton loading components with shimmer animation.
 */

const SIDEBAR_WIDTHS = ["75%", "45%", "65%", "55%", "80%"];
const EXPLORER_WIDTHS = ["60%", "45%", "70%", "50%"];
const EDITOR_WIDTHS = ["85%", "60%", "75%", "45%", "90%", "55%", "70%", "50%", "80%", "65%", "40%", "95%"];

function SkeletonLine({ width = "100%", className = "" }: { width?: string; className?: string }) {
  return (
    <div
      className={`h-3 rounded bg-border animate-pulse ${className}`}
      style={{ width }}
    />
  );
}

function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div className={`rounded-lg bg-border animate-pulse ${className}`} />
  );
}

/** Skeleton for the sidebar project list (5 items) */
export function SkeletonSidebar() {
  return (
    <div className="flex-1 overflow-y-auto py-2 px-2 space-y-2">
      {SIDEBAR_WIDTHS.map((width, i) => (
        <div key={i} className="flex flex-col gap-1.5 px-3 py-2">
          <SkeletonLine width={width} />
          <SkeletonLine width="30%" className="h-2" />
        </div>
      ))}
    </div>
  );
}

/** Skeleton for the file explorer tree (4 items) */
export function SkeletonExplorer() {
  return (
    <div className="flex-1 overflow-y-auto py-2 px-3 space-y-2">
      {EXPLORER_WIDTHS.map((width, i) => (
        <div key={i} className="flex items-center gap-2" style={{ paddingLeft: `${(i % 3) * 12}px` }}>
          <SkeletonLine width="12px" className="h-3" />
          <SkeletonLine width={width} className="h-3" />
        </div>
      ))}
    </div>
  );
}

/** Skeleton for the editor area */
export function SkeletonEditor() {
  return (
    <div className="flex-1 flex flex-col p-4 gap-3">
      {/* Tab bar skeleton */}
      <div className="flex items-center gap-1">
        <SkeletonBlock className="h-8 w-20" />
        <SkeletonBlock className="h-8 w-16" />
        <SkeletonBlock className="h-8 w-24" />
      </div>
      {/* Editor lines skeleton */}
      <div className="flex-1 flex flex-col gap-2.5 pt-4">
        {EDITOR_WIDTHS.map((width, i) => (
          <SkeletonLine key={i} width={width} className="h-3" />
        ))}
      </div>
    </div>
  );
}
