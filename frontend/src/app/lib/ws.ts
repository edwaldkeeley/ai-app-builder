import type { ProjectFile } from "./types";

// ── WebSocket streaming client ────────────────────────────────

export interface StreamCallbacks {
  onMessageChunk?: (delta: string) => void;
  onFileStart?: (path: string, fileType: string) => void;
  onFileChunk?: (path: string, delta: string) => void;
  onFileDone?: (path: string) => void;
  onProject?: (projectId: string, projectName: string) => void;
  onDone?: (message: string, files: ProjectFile[]) => void;
  onError?: (detail: string, retryAfter?: number) => void;
}

export interface StreamSession {
  send: (prompt: string, projectId?: string, framework?: string) => void;
  close: () => void;
}

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function generateStream(callbacks: StreamCallbacks): StreamSession {
  let ws: WebSocket | null = null;
  let closed = false;

  const connect = (prompt: string, projectId?: string, framework?: string) => {
    if (closed) return;

    ws = new WebSocket(`${WS_BASE}/api/ai/ws/generate`);

    ws.onopen = () => {
      ws?.send(JSON.stringify({
        type: "generate",
        prompt,
        project_id: projectId || null,
        framework: framework || "vanilla",
      }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case "message_chunk":
            callbacks.onMessageChunk?.(msg.delta);
            break;
          case "file_start":
            callbacks.onFileStart?.(msg.path, msg.file_type);
            break;
          case "file_chunk":
            callbacks.onFileChunk?.(msg.path, msg.delta);
            break;
          case "file_done":
            callbacks.onFileDone?.(msg.path);
            break;
          case "project":
            callbacks.onProject?.(msg.project_id, msg.project_name);
            break;
          case "done":
            callbacks.onDone?.(msg.message, msg.files);
            break;
          case "error":
            callbacks.onError?.(msg.detail, msg.retry_after);
            break;
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      if (!closed) {
        callbacks.onError?.("WebSocket connection failed. Falling back to REST.");
      }
    };

    ws.onclose = () => {
      // No-op; session is done
    };
  };

  return {
    send: (prompt: string, projectId?: string, framework?: string) => {
      connect(prompt, projectId, framework);
    },
    close: () => {
      closed = true;
      ws?.close();
      ws = null;
    },
  };
}
