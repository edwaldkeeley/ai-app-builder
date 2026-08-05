"use client";

/**
 * Spinner — consistent loading indicator. Defaults to accent color, 16x16.
 */
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
