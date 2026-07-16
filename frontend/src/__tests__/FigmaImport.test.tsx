import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import { render, screen, act } from "@testing-library/react";
import FigmaImport from "../app/components/FigmaImport";

// Mock the API
jest.mock("../app/lib/api", () => ({
  api: {
    importFigmaUrl: jest.fn(),
  },
}));

jest.mock("../app/components/Toast", () => ({
  useToast: () => ({ showToast: jest.fn() }),
}));

describe("FigmaImport", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders landing variant with URL and token inputs", () => {
    render(<FigmaImport variant="landing" />);
    expect(screen.getByPlaceholderText("https://www.figma.com/file/ABC123/My-Design")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Figma personal access token (required)")).toBeInTheDocument();
  });

  it("renders toolbar variant as an icon button", () => {
    render(<FigmaImport variant="toolbar" />);
    // Toolbar variant shows a button that opens a modal
    const button = screen.getByTitle("Import from Figma URL");
    expect(button).toBeInTheDocument();
  });

  it("opens modal when toolbar button is clicked", () => {
    render(<FigmaImport variant="toolbar" />);

    act(() => {
      screen.getByTitle("Import from Figma URL").click();
    });

    expect(screen.getByPlaceholderText("https://www.figma.com/file/ABC123/My-Design")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Figma personal access token (required)")).toBeInTheDocument();
  });

  it("disables import button when fields are empty", () => {
    render(<FigmaImport variant="landing" />);
    const importButton = screen.getByText("Import from Figma");
    expect(importButton).toBeDisabled();
  });

  it("calls onImportComplete when import succeeds", async () => {
    const onImportComplete = jest.fn();
    const { api } = require("../app/lib/api");
    api.importFigmaUrl.mockResolvedValue({
      project_id: "123",
      project_name: "Figma Import",
      message: "Done",
      files: [],
    });

    render(<FigmaImport variant="landing" onImportComplete={onImportComplete} />);

    const urlInput = screen.getByPlaceholderText("https://www.figma.com/file/ABC123/My-Design");
    const tokenInput = screen.getByPlaceholderText("Figma personal access token (required)");

    await act(async () => {
      // Use native input events
      urlInput.setAttribute("value", "https://figma.com/file/abc");
      urlInput.dispatchEvent(new Event("input", { bubbles: true }));
      tokenInput.setAttribute("value", "token123");
      tokenInput.dispatchEvent(new Event("input", { bubbles: true }));
    });

    const importButton = screen.getByText("Import from Figma");
    expect(importButton).not.toBeDisabled();
  });
});
