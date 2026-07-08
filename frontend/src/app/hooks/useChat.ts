"use client";

import { useState, useCallback, useRef } from "react";
import { api, generateStream } from "../lib/api";
import type { ChatMessage, ProjectFile } from "../lib/types";
import { useToast } from "../components/Toast";

// Use a ref-based counter per hook instance instead of module-level
// to avoid key collision across projects and page navigations

export type WritingStatus = {
  type: "thinking" | "writing" | "fixing" | "done";
  file?: string;
  message?: string;
};

export function useChat() {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [generating, setGenerating] = useState(false);
  const [chatMode, setChatMode] = useState(false);
  const [writingStatus, setWritingStatus] = useState<WritingStatus | null>(null);
  const chatIdCounterRef = useRef(0);
  const loadRequestIdRef = useRef(0);
  const generatingRef = useRef(false);
  const { showToast } = useToast();

  const saveMessage = useCallback(
    async (projectId: string, role: string, content: string, files?: ProjectFile[]) => {
      try {
        await api.saveChatMessage(projectId, role, content, files);
      } catch (err) {
        console.error("Failed to save chat message:", err);
        showToast("error", "Failed to save message");
      }
    },
    [showToast],
  );

  const loadChatMessages = useCallback(async (projectId: string) => {
    const requestId = ++loadRequestIdRef.current;
    try {
      const msgs = await api.getChatMessages(projectId);
      // Only apply if this is still the latest request
      if (requestId !== loadRequestIdRef.current) return;
      // Guard: if we already have messages for this project and the count matches,
      // don't re-set state (prevents duplication from React Strict Mode double-fire)
      if (chatMessages.length > 0 && msgs.length > 0) {
        const lastExisting = chatMessages[chatMessages.length - 1];
        const lastFetched = msgs[msgs.length - 1];
        if (lastExisting.id === `chat-${lastFetched.id}`) return;
      }
      const converted: ChatMessage[] = msgs.map((m) => ({
        id: `chat-${m.id}`,
        role: m.role as "user" | "assistant",
        content: m.content,
        files: m.files,
        timestamp: m.created_at,
      }));
      setChatMessages(converted);
      const maxId = msgs.reduce((max, m) => Math.max(max, m.id), 0);
      chatIdCounterRef.current = maxId + 1;
    } catch {
      // Silently fail
    }
  }, [chatMessages]);

  const clearChatMessages = useCallback(() => {
    setChatMessages([]);
  }, []);

  const handlePrompt = useCallback(
    async (
      prompt: string,
      projectId: string,
      files: ProjectFile[],
      setFiles: React.Dispatch<React.SetStateAction<ProjectFile[]>>,
      fetchProjects: () => void,
      setError: (err: string | null) => void,
    ) => {
      // Use ref-based guard to prevent double-invocation before React re-renders
      if (generatingRef.current) return;
      generatingRef.current = true;

      setGenerating(true);
      setWritingStatus({ type: "thinking", message: "Generating response..." });

      // Add user message
      const userMsg: ChatMessage = {
        id: `chat-${++chatIdCounterRef.current}`,
        role: "user",
        content: prompt,
        timestamp: new Date().toISOString(),
      };
      setChatMessages((prev) => [...prev, userMsg]);
      await saveMessage(projectId, "user", prompt);

      // Create a placeholder AI message
      const aiMsgId = `chat-${++chatIdCounterRef.current}`;
      const aiMessage: ChatMessage = {
        id: aiMsgId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
      };
      setChatMessages((prev) => [...prev, aiMessage]);

      // Track streaming state
      let streamedContent = "";
      let displayContent = "";  // cleaned-up version for display
      const streamedFiles = new Map<string, string>();
      let resolvedProjectId = projectId;
      let streamError: string | null = null;

      // Strip JSON wrapper characters from streaming content to show clean message text.
      // The AI generates: {"message": "Hello...", "files": [...]}
      // We strip: leading '{"message": "' and trailing '", "files":' or '"}
      const stripJsonWrapper = (raw: string): string => {
        let cleaned = raw;
        // Strip leading JSON keys: {"message": "  or  "message": "
        const msgPrefixMatch = cleaned.match(/^\s*\{?\s*"message"\s*:\s*"/);
        if (msgPrefixMatch) {
          cleaned = cleaned.slice(msgPrefixMatch[0].length);
        }
        // Strip trailing JSON: ", "files":  or  "}  or  "]  etc
        // Only strip if it looks like JSON structure, not actual content
        const fileSuffixMatch = cleaned.match(/",\s*"files"\s*:/);
        if (fileSuffixMatch) {
          cleaned = cleaned.slice(0, fileSuffixMatch.index);
        }
        // Strip trailing quote + closing brace
        cleaned = cleaned.replace(/"\s*\}\s*$/, "");
        return cleaned;
      };

      const streamComplete = new Promise<void>((resolve) => {
        const session = generateStream({
          onMessageChunk: (delta) => {
            streamedContent += delta;
            // Clean up the display content by stripping JSON wrappers
            displayContent = stripJsonWrapper(streamedContent);
            setChatMessages((prev) => {
              const updated = [...prev];
              const idx = updated.findIndex((m) => m.id === aiMsgId);
              if (idx !== -1) {
                updated[idx] = { ...updated[idx], content: displayContent };
              }
              return updated;
            });
            // Switch from "thinking" to showing the message is streaming
            setWritingStatus((prev) => {
              if (prev?.type === "thinking") {
                return { type: "writing", file: "response", message: "Streaming response..." };
              }
              return prev;
            });
            // Note: "fixing" status is set by the backend when it detects
            // and auto-fixes issues in the generated code
          },
          onFileStart: (path, _fileType) => {
            streamedFiles.set(path, "");
            setFiles((prev) => {
              if (prev.some((f) => f.path === path)) return prev;
              return [...prev, { path, content: "", file_type: _fileType as ProjectFile["file_type"] }];
            });
            setWritingStatus({ type: "writing", file: path });
          },
          onFileChunk: (_path, _delta) => {
            const existing = streamedFiles.get(_path) || "";
            const updated = existing + _delta;
            streamedFiles.set(_path, updated);
            setFiles((prev) =>
              prev.map((f) =>
                f.path === _path ? { ...f, content: updated } : f,
              ),
            );
          },
          onFileDone: () => {},
          onProject: (id) => {
            resolvedProjectId = id;
          },
          onDone: (message, generatedFiles) => {
            const finalContent = message || streamedContent || `Generated ${generatedFiles.length} file${generatedFiles.length !== 1 ? "s" : ""}`;
            setChatMessages((prev) => {
              const updated = [...prev];
              const idx = updated.findIndex((m) => m.id === aiMsgId);
              if (idx !== -1) {
                updated[idx] = { ...updated[idx], content: finalContent, files: generatedFiles };
              }
              return updated;
            });
            saveMessage(resolvedProjectId, "assistant", finalContent, generatedFiles);
            fetchProjects();
            setWritingStatus({ type: "done", message: "Complete" });
            generatingRef.current = false;
            setGenerating(false);
            session.close();
            resolve();
          },
          onError: (detail, retryAfter) => {
            streamError = detail;
            if (retryAfter && retryAfter > 0) {
              const mins = Math.floor(retryAfter / 60);
              const secs = retryAfter % 60;
              const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
              streamError = `Rate limited — retry in ${timeStr}: ${detail}`;
            }
            session.close();
            resolve();
          },
        });

        // Timeout: if WebSocket doesn't complete in 60s, fall back to REST
        const timeoutId = setTimeout(() => {
          streamError = streamError || "WebSocket timed out";
          session.close();
          resolve();
        }, 60000);

        // Clear timeout if promise resolves naturally
        // (onDone and onError already call resolve, so we hook into session.close)
        const clearTimer = () => clearTimeout(timeoutId);
        const origClose = session.close.bind(session);
        session.close = () => { clearTimer(); origClose(); };

        session.send(prompt, projectId);
      });

      await streamComplete;

      // Fall back to REST if WebSocket failed
      if (streamError) {
        showToast("info", "WebSocket timed out, falling back to REST...");
        try {
          setWritingStatus({ type: "thinking", message: "Falling back to REST..." });
          const result = await api.generate(prompt, resolvedProjectId);
          const finalContent = result.message || `Generated ${result.files.length} file${result.files.length !== 1 ? "s" : ""}`;
          setChatMessages((prev) => {
            const updated = [...prev];
            const idx = updated.findIndex((m) => m.id === aiMsgId);
            if (idx !== -1) {
              updated[idx] = { ...updated[idx], content: finalContent, files: result.files };
            }
            return updated;
          });
          saveMessage(resolvedProjectId, "assistant", finalContent, result.files);
          setFiles(result.files);
          await fetchProjects();
          setWritingStatus({ type: "done", message: "Complete" });
        } catch (err) {
          const msg = err instanceof Error ? err.message : "AI generation failed";
          setError(msg);
          setChatMessages((prev) => {
            const updated = [...prev];
            const idx = updated.findIndex((m) => m.id === aiMsgId);
            if (idx !== -1) {
              updated[idx] = { ...updated[idx], content: `Error: ${msg}` };
            }
            return updated;
          });
        } finally {
          setWritingStatus(null);
          generatingRef.current = false;
            setGenerating(false);
        }
      } else {
        // WebSocket succeeded but onDone may not have fired (edge case)
        generatingRef.current = false;
            setGenerating(false);
      }
    },
    [saveMessage, showToast],
  );

  return {
    chatMessages,
    setChatMessages,
    generating,
    setGenerating,
    chatMode,
    setChatMode,
    writingStatus,
    saveMessage,
    loadChatMessages,
    clearChatMessages,
    handlePrompt,
  };
}
