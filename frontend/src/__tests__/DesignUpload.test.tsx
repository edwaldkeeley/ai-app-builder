import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import { render, screen, act } from "@testing-library/react";
import DesignUpload from "../app/components/DesignUpload";

// Mock the API
jest.mock("../app/lib/api", () => ({
  api: {
    uploadDesign: jest.fn(),
  },
}));

jest.mock("../app/components/Toast", () => ({
  useToast: () => ({ showToast: jest.fn() }),
}));

describe("DesignUpload", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders landing variant with upload area", () => {
    render(<DesignUpload variant="landing" projectId="" />);
    expect(screen.getByText("Design Upload")).toBeInTheDocument();
  });

  it("renders toolbar variant as an icon button", () => {
    render(<DesignUpload variant="toolbar" projectId="1" />);
    const button = screen.getByTitle("Upload a design image");
    expect(button).toBeInTheDocument();
  });

  it("opens modal when toolbar button is clicked", () => {
    render(<DesignUpload variant="toolbar" projectId="1" />);

    act(() => {
      screen.getByTitle("Upload a design image").click();
    });

    expect(screen.getByText("Upload Design Image")).toBeInTheDocument();
  });
});
