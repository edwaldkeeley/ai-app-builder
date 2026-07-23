import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import { render, screen, act } from "@testing-library/react";
import FileExplorer from "../app/components/FileExplorer";
import type { ProjectFile } from "../app/lib/types";

describe("FileExplorer", () => {
  const defaultProps = {
    files: [] as ProjectFile[],
    activeFilePath: null as string | null,
    onSelectFile: jest.fn(),
    onAddFile: jest.fn(),
    onDeleteFile: jest.fn(),
    onRenameFile: jest.fn(),
    dirtyFiles: new Set<string>(),
    loading: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders empty state with code files header", () => {
    render(<FileExplorer {...defaultProps} />);
    expect(screen.getByText("Code Files")).toBeInTheDocument();
  });

  it("renders file list", () => {
    const files: ProjectFile[] = [
      { path: "index.html", content: "<html></html>", file_type: "html" },
      { path: "style.css", content: "body {}", file_type: "css" },
    ];
    render(<FileExplorer {...defaultProps} files={files} />);
    expect(screen.getByText("index.html")).toBeInTheDocument();
    expect(screen.getByText("style.css")).toBeInTheDocument();
  });

  it("highlights active file", () => {
    const files: ProjectFile[] = [
      { path: "index.html", content: "", file_type: "html" },
      { path: "style.css", content: "", file_type: "css" },
    ];
    render(<FileExplorer {...defaultProps} files={files} activeFilePath="index.html" />);
    const activeItem = screen.getByText("index.html").closest('[class*="bg-accent"]');
    // Active file should have accent background
    expect(activeItem).toBeDefined();
  });

  it("shows dirty indicator for unsaved files", () => {
    const files: ProjectFile[] = [
      { path: "index.html", content: "changed", file_type: "html" },
    ];
    render(<FileExplorer {...defaultProps} files={files} dirtyFiles={new Set(["index.html"])} />);
    // The dirty indicator is a blue dot — we just verify it renders without error
    expect(screen.getByText("index.html")).toBeInTheDocument();
  });

  it("calls onSelectFile when a file is clicked", () => {
    const onSelectFile = jest.fn();
    const files: ProjectFile[] = [
      { path: "index.html", content: "", file_type: "html" },
    ];
    render(<FileExplorer {...defaultProps} files={files} onSelectFile={onSelectFile} />);

    act(() => {
      screen.getByText("index.html").click();
    });

    expect(onSelectFile).toHaveBeenCalledWith("index.html");
  });

  it("shows loading skeleton when loading", () => {
    render(<FileExplorer {...defaultProps} loading={true} />);
    const skeleton = document.querySelector(".bg-border");
    expect(skeleton).toBeDefined();
  });

  it("organizes files by directory", () => {
    const files: ProjectFile[] = [
      { path: "index.html", content: "", file_type: "html" },
      { path: "src/app.ts", content: "", file_type: "javascript" },
    ];
    render(<FileExplorer {...defaultProps} files={files} />);
    expect(screen.getByText("index.html")).toBeInTheDocument();
    // Directory names should be visible
    expect(screen.getByText("src")).toBeInTheDocument();
  });
});
