"use client";

/**
 * Shared UI primitives for consistent rendering across the app.
 */

/** Spinner — consistent loading indicator. Defaults to accent color, 16x16. */
export function Spinner({
  className = "w-4 h-4",
  color = "accent",
}: {
  className?: string;
  color?: string;
}) {
  return (
    <span
      className={`border-2 border-${color} border-t-transparent rounded-full animate-spin ${className}`}
      aria-label="Loading"
      role="status"
    />
  );
}

/** BouncingDots — animated dots for "thinking" / "writing" states. */
export function BouncingDots() {
  return (
    <span className="flex gap-0.5">
      <span
        className="w-1 h-1 bg-text-secondary rounded-full animate-bounce"
        style={{ animationDelay: "0ms" }}
      />
      <span
        className="w-1 h-1 bg-text-secondary rounded-full animate-bounce"
        style={{ animationDelay: "150ms" }}
      />
      <span
        className="w-1 h-1 bg-text-secondary rounded-full animate-bounce"
        style={{ animationDelay: "300ms" }}
      />
    </span>
  );
}
