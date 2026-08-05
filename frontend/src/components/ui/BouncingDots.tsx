"use client";

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
