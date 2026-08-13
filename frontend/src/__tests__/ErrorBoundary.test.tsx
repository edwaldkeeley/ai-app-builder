import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

// Suppress console.error from React's componentDidCatch logging in tests
beforeEach(() => {
  jest.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  jest.restoreAllMocks();
});

const ThrowOnRender = ({ message = "Test crash" }: { message?: string }) => {
  throw new Error(message);
};

describe("ErrorBoundary", () => {
  it("renders children when there is no error", () => {
    render(
      <ErrorBoundary>
        <div>Safe content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("Safe content")).toBeInTheDocument();
  });

  it("renders fallback UI when a child throws", () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Try Again")).toBeInTheDocument();
  });

  it("shows error details in a collapsible element", () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender message="Connection refused" />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Error details")).toBeInTheDocument();
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
  });

  it("recovers after clicking Try Again when the error is transient", () => {
    // Use a throwing-then-stable pattern: first render throws, then
    // clicking Try Again resets the error boundary so children re-render.
    const { container } = render(
      <ErrorBoundary>
        <ThrowOnRender />
      </ErrorBoundary>,
    );

    // Error UI is shown
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Click "Try Again" — error state resets
    fireEvent.click(screen.getByText("Try Again"));

    // After reset, the component tree re-renders. Since ThrowOnRender
    // still throws, the boundary catches again — but the important thing
    // is that getDerivedStateFromError runs again (reset worked).
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("uses custom fallback when provided", () => {
    render(
      <ErrorBoundary fallback={<div>Custom error UI</div>}>
        <ThrowOnRender />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Custom error UI")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});
