import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatPanel from "../app/components/ChatPanel";
import type { ChatMessage } from "../app/lib/types";

// ── Mock dependencies ─────────────────────────────────────
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}));

jest.mock("remark-gfm", () => () => {});

jest.mock("../app/components/FigmaImport", () => ({
  __esModule: true,
  default: () => <div data-testid="figma-import" />,
}));

jest.mock("../app/components/DesignUpload", () => ({
  __esModule: true,
  default: () => <div data-testid="design-upload" />,
}));

describe("ChatPanel", () => {
  const defaultProps = {
    messages: [] as ChatMessage[],
    onSend: jest.fn(),
    disabled: false,
    generating: false,
    writingStatus: null,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders empty state", () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByText("Ask the AI to build something")).toBeInTheDocument();
  });

  it("renders user messages", () => {
    const messages: ChatMessage[] = [
      { id: "1", role: "user", content: "Hello", timestamp: "2026-01-01T00:00:00Z" },
    ];
    render(<ChatPanel {...defaultProps} messages={messages} />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("You")).toBeInTheDocument();
  });

  it("renders AI messages with markdown", () => {
    const messages: ChatMessage[] = [
      { id: "1", role: "assistant", content: "**bold** text", timestamp: "2026-01-01T00:00:00Z" },
    ];
    render(<ChatPanel {...defaultProps} messages={messages} />);
    expect(screen.getByText("AI")).toBeInTheDocument();
    expect(screen.getByTestId("markdown")).toBeInTheDocument();
  });

  it("shows file count for AI messages with files", () => {
    const messages: ChatMessage[] = [
      {
        id: "1", role: "assistant", content: "Done",
        files: [{ path: "index.html", content: "", file_type: "html" }],
        timestamp: "2026-01-01T00:00:00Z",
      },
    ];
    render(<ChatPanel {...defaultProps} messages={messages} />);
    expect(screen.getByText("1 file generated")).toBeInTheDocument();
  });

  it("calls onSend when send button is clicked", async () => {
    const onSend = jest.fn();
    render(<ChatPanel {...defaultProps} onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Describe what you want to build...");
    await userEvent.type(textarea, "build a site");

    const sendButton = screen.getByLabelText("Send message");
    await userEvent.click(sendButton);

    expect(onSend).toHaveBeenCalledWith("build a site");
  });

  it("calls onSend on Enter key", async () => {
    const onSend = jest.fn();
    render(<ChatPanel {...defaultProps} onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Describe what you want to build...");
    await userEvent.type(textarea, "hello{Enter}");

    expect(onSend).toHaveBeenCalledWith("hello");
  });

  it("does not call onSend when disabled", async () => {
    const onSend = jest.fn();
    render(<ChatPanel {...defaultProps} onSend={onSend} disabled={true} />);

    const textarea = screen.getByPlaceholderText("Describe what you want to build...");
    await userEvent.type(textarea, "hello{Enter}");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend when generating", async () => {
    const onSend = jest.fn();
    render(<ChatPanel {...defaultProps} onSend={onSend} generating={true} />);

    const textarea = screen.getByPlaceholderText("Describe what you want to build...");
    await userEvent.type(textarea, "hello{Enter}");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables textarea and button when generating", () => {
    render(<ChatPanel {...defaultProps} generating={true} />);

    const textarea = screen.getByPlaceholderText("Describe what you want to build...");
    expect(textarea).toBeDisabled();

    const sendButton = screen.getByLabelText("Send message");
    expect(sendButton).toBeDisabled();
  });

  it("shows writing indicator when generating", () => {
    render(
      <ChatPanel
        {...defaultProps}
        generating={true}
        writingStatus={{ type: "thinking", message: "Analyzing request" }}
      />,
    );
    expect(screen.getByText("Analyzing request")).toBeInTheDocument();
  });

  it("shows writing file status", () => {
    render(
      <ChatPanel
        {...defaultProps}
        generating={true}
        writingStatus={{ type: "writing", file: "index.html" }}
      />,
    );
    expect(screen.getByText("index.html")).toBeInTheDocument();
    expect(screen.getByText("writing...")).toBeInTheDocument();
  });

  it("shows generation complete status", () => {
    render(
      <ChatPanel
        {...defaultProps}
        generating={true}
        writingStatus={{ type: "done", message: "Complete" }}
      />,
    );
    expect(screen.getByText("Generation complete")).toBeInTheDocument();
  });

  it("has accessible chat log region", () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByRole("log")).toBeInTheDocument();
    expect(screen.getByLabelText("Chat messages")).toBeInTheDocument();
  });

  it("has accessible send button", () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByLabelText("Send message")).toBeInTheDocument();
  });
});
