import { describe, it, expect } from "@jest/globals";
import { render, screen } from "@testing-library/react";
import { SkeletonSidebar, SkeletonExplorer, SkeletonEditor } from "../app/components/Skeleton";

describe("SkeletonSidebar", () => {
  it("renders skeleton items", () => {
    const { container } = render(<SkeletonSidebar />);
    const items = container.querySelectorAll(".bg-border");
    expect(items.length).toBeGreaterThan(0);
  });
});

describe("SkeletonExplorer", () => {
  it("renders skeleton tree items", () => {
    const { container } = render(<SkeletonExplorer />);
    const items = container.querySelectorAll(".bg-border");
    expect(items.length).toBeGreaterThan(0);
  });
});

describe("SkeletonEditor", () => {
  it("renders skeleton editor layout", () => {
    const { container } = render(<SkeletonEditor />);
    const items = container.querySelectorAll(".bg-border");
    expect(items.length).toBeGreaterThan(0);
  });
});
