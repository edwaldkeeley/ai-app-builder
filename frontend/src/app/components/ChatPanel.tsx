"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../lib/types";
import type { WritingStatus } from "../hooks/useChat";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (prompt: string) => void;
  disabled?: boolean;
  generating?: boolean;
  writingStatus?: WritingStatus | null;
}

function WritingIndicator({ status }: { status: WritingStatus }) {
  return (
    <div className="flex items-start gap-2.5 text-xs text-text-secondary py-1">
      {/* Animated icon */}
      {status.type === "done" ? (
        <span className="mt-0.5 text-green-500">✓</span>
      ) : (
        <span className="mt-0.5 w-3.5 h-3.5 border-2 border-accent border-t-transparent rounded-full animate-spin flex-shrink-0" aria-label="Loading" />
      )}

      <div className="flex flex-col gap-1 min-w-0">
        {status.type === "thinking" && (
          <div className="flex items-center gap-1.5">
            <span className="text-foreground font-medium">Analyzing request</span>
            <span className="flex gap-0.5">
              <span className="w-1 h-1 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1 h-1 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1 h-1 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </span>
          </div>
        )}

        {status.type === "writing" && (
          <div className="flex items-center gap-2">
            <span className="text-accent font-mono text-[11px]">▸</span>
            <code className="px-1.5 py-0.5 rounded bg-accent/10 text-accent font-mono text-[11px] font-medium truncate max-w-[200px]">
              {status.file}
            </code>
            <span className="text-text-secondary/60">writing...</span>
          </div>
        )}

        {status.type === "fixing" && (
          <div className="flex items-center gap-1.5">
            <span className="text-amber-500">🔧</span>
            <span className="text-amber-600 dark:text-amber-400 font-medium">
              {status.message || "Fixing issues..."}
            </span>
          </div>
        )}

        {status.type === "done" && (
          <div className="flex items-center gap-1.5">
            <span className="text-green-600 dark:text-green-400 font-medium">Generation complete</span>
            {status.message && (
              <span className="text-text-secondary">— {status.message}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatPanel({
  messages,
  onSend,
  disabled,
  generating,
  writingStatus,
}: ChatPanelProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  }, [value]);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled || generating) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background border-r border-border">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-sidebar/50">
        <div className="w-5 h-5 rounded-md bg-accent flex items-center justify-center flex-shrink-0">
          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        </div>
        <span className="text-sm font-semibold">Chat</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-4" role="log" aria-live="polite" aria-label="Chat messages">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center mb-3">
              <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <p className="text-sm text-text-secondary">Ask the AI to build something</p>
            <p className="text-xs text-text-secondary mt-1">
              Describe what you want and AI will generate the code.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold uppercase tracking-wider ${
                  msg.role === "user" ? "text-accent" : "text-text-secondary"
                }`}>
                  {msg.role === "user" ? "You" : "AI"}
                </span>
                <span className="text-[10px] text-text-secondary">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className={`prose prose-sm max-w-none ${
                msg.role === "user"
                  ? "bg-accent/10 text-foreground rounded-lg px-3 py-2"
                  : "text-foreground"
              }`}>
                {msg.role === "user" ? (
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                ) : (
                  <div className="text-sm leading-relaxed [&_pre]:bg-surface [&_pre]:border [&_pre]:border-border [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_code]:text-xs [&_code]:font-mono [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_a]:text-accent [&_a]:underline [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:text-sm [&_h3]:font-medium [&_p]:mb-2 [&_li]:mb-0.5">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
              {msg.files && msg.files.length > 0 && (
                <p className="text-xs text-accent">
                  {msg.files.length} file{msg.files.length !== 1 ? "s" : ""} generated
                </p>
              )}
            </div>
          ))
        )}
        {generating && writingStatus && (
          <WritingIndicator status={writingStatus} />
        )}
        <div ref={bottomRef} />
      </div>

      {/* Prompt input */}
      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2 bg-input border border-border rounded-xl px-3 py-2 focus-within:border-accent/50 focus-within:ring-1 focus-within:ring-accent/20 transition-all">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe what you want to build..."
            rows={1}
            disabled={disabled || generating}
            className="flex-1 bg-transparent text-sm text-foreground placeholder-text-secondary resize-none outline-none focus-visible:outline-none max-h-[200px]"
          />
          <button
            onClick={handleSend}
            disabled={!value.trim() || disabled || generating}
            aria-label="Send message"
            className="flex-shrink-0 p-1.5 rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
        <p className="text-[10px] text-text-secondary text-center mt-1.5">
          AI-generated code may not always be perfect. Review and test before using.
        </p>
      </div>
    </div>
  );
}
