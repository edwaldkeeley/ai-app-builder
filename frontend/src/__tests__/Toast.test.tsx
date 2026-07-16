import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import { render, screen, act } from "@testing-library/react";
import { ToastProvider, useToast } from "../app/components/Toast";

// Helper component to trigger toasts
function ToastTrigger({ type, message }: { type: "success" | "error" | "info"; message: string }) {
  const { showToast } = useToast();
  return <button onClick={() => showToast(type, message)}>Show Toast</button>;
}

describe("Toast", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("renders children", () => {
    render(
      <ToastProvider>
        <div>Child</div>
      </ToastProvider>,
    );
    expect(screen.getByText("Child")).toBeInTheDocument();
  });

  it("shows a success toast", () => {
    render(
      <ToastProvider>
        <ToastTrigger type="success" message="Saved!" />
      </ToastProvider>,
    );

    act(() => {
      screen.getByText("Show Toast").click();
    });

    expect(screen.getByText("Saved!")).toBeInTheDocument();
  });

  it("shows an error toast", () => {
    render(
      <ToastProvider>
        <ToastTrigger type="error" message="Failed!" />
      </ToastProvider>,
    );

    act(() => {
      screen.getByText("Show Toast").click();
    });

    expect(screen.getByText("Failed!")).toBeInTheDocument();
  });

  it("shows an info toast", () => {
    render(
      <ToastProvider>
        <ToastTrigger type="info" message="Loading..." />
      </ToastProvider>,
    );

    act(() => {
      screen.getByText("Show Toast").click();
    });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("auto-dismisses toast after timeout", () => {
    render(
      <ToastProvider>
        <ToastTrigger type="info" message="Will disappear" />
      </ToastProvider>,
    );

    act(() => {
      screen.getByText("Show Toast").click();
    });

    expect(screen.getByText("Will disappear")).toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(5000);
    });

    expect(screen.queryByText("Will disappear")).not.toBeInTheDocument();
  });
});
