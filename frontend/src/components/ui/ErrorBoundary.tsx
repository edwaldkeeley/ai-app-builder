"use client";

import React from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Optional fallback UI. If omitted, shows a default error screen. */
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Catches unhandled render errors in its subtree and displays a fallback UI
 * instead of crashing the entire page.
 *
 * Includes a "Try Again" button that resets state so the subtree re-renders.
 * Logs the error to the console for debugging.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("[ErrorBoundary] Unhandled error:", error);
    console.error("[ErrorBoundary] Component stack:", errorInfo.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex items-center justify-center h-dvh bg-[var(--color-background)] text-[var(--color-foreground)] p-8">
          <div className="max-w-md text-center space-y-4">
            <div className="text-4xl" role="img" aria-label="warning sign">
              ⚠️
            </div>
            <h1 className="text-xl font-semibold">Something went wrong</h1>
            <p className="text-sm text-[var(--color-text-secondary)]">
              An unexpected error occurred while rendering this page.
            </p>
            {this.state.error && (
              <details className="text-left text-xs text-[var(--color-text-secondary)] bg-[var(--color-surface)] rounded p-3 max-h-32 overflow-auto">
                <summary className="cursor-pointer font-medium mb-1">Error details</summary>
                <pre className="whitespace-pre-wrap break-all">{this.state.error.message}</pre>
              </details>
            )}
            <button
              onClick={this.handleRetry}
              className="px-4 py-2 rounded bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
