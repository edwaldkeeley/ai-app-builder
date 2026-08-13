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

/** Number of reconnection attempts before giving up. */
const MAX_RECONNECT_ATTEMPTS = 3;
/** Delay between reconnection attempts (milliseconds). */
const RECONNECT_DELAY_MS = 1500;

export function generateStream(callbacks: StreamCallbacks): StreamSession {
  let ws: WebSocket | null = null;
  let closed = false;
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const cleanup = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const connect = (prompt: string, projectId?: string, framework?: string) => {
    if (closed) return;

    ws = new WebSocket(`${WS_BASE}/api/ai/ws/generate`);

    ws.onopen = () => {
      // Reset reconnect counter on successful connection
      reconnectAttempts = 0;
      ws?.send(
        JSON.stringify({
          type: "generate",
          prompt,
          project_id: projectId || null,
          framework: framework || "vanilla",
        }),
      );
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
            cleanup();
            callbacks.onDone?.(msg.message, msg.files);
            break;
          case "error":
            cleanup();
            callbacks.onError?.(msg.detail, msg.retry_after);
            break;
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      // onerror fires before onclose, so we handle reconnection in onclose
    };

    ws.onclose = (event) => {
      if (closed) return; // intentional close — no reconnect
      if (event.code === 1000) return; // normal closure — no reconnect

      // If we already received a "done" or "error" event, don't reconnect
      // (the WS closes normally after those events are sent).
      // Unexpected close: attempt reconnection.
      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        console.warn(
          `WebSocket closed unexpectedly (code=${event.code}). Reconnecting in ${RECONNECT_DELAY_MS}ms (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`,
        );
        reconnectTimer = setTimeout(
          () => connect(prompt, projectId, framework),
          RECONNECT_DELAY_MS,
        );
      } else {
        cleanup();
        callbacks.onError?.(
          `WebSocket connection failed after ${MAX_RECONNECT_ATTEMPTS} attempts. Falling back to REST.`,
        );
      }
    };
  };

  return {
    send: (prompt: string, projectId?: string, framework?: string) => {
      connect(prompt, projectId, framework);
    },
    close: () => {
      closed = true;
      cleanup();
      ws?.close();
      ws = null;
    },
  };
}
