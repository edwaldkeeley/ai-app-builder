import type { ChatMessageSchema, GenerateResponse, Project, ProjectDetail, ProjectFile, SandboxState } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

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
  send: (prompt: string, projectId?: string) => void;
  close: () => void;
}

export function generateStream(callbacks: StreamCallbacks): StreamSession {
  let ws: WebSocket | null = null;
  let closed = false;

  const connect = (prompt: string, projectId?: string) => {
    if (closed) return;

    ws = new WebSocket(`${WS_BASE}/api/ai/ws/generate`);

    ws.onopen = () => {
      ws?.send(JSON.stringify({
        type: "generate",
        prompt,
        project_id: projectId || null,
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
    send: (prompt: string, projectId?: string) => {
      connect(prompt, projectId);
    },
    close: () => {
      closed = true;
      ws?.close();
      ws = null;
    },
  };
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit, timeoutMs = 120000): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });

    if (!res.ok) {
      let detail = `Request failed: ${res.status}`;
      let retryAfter: number | undefined;

      // Parse Retry-After header first (most reliable)
      const retryHeader = res.headers.get("Retry-After");
      if (retryHeader) {
        const parsed = parseInt(retryHeader, 10);
        if (!isNaN(parsed)) retryAfter = parsed;
      }

      // Then try JSON body for more detail
      try {
        const body = await res.json();
        if (body?.detail) {
          if (typeof body.detail === "object" && body.detail !== null) {
            detail = body.detail.message ?? String(body.detail);
            if (body.detail.retry_after != null) retryAfter = body.detail.retry_after;
          } else {
            detail = body.detail;
          }
        }
        if (body?.retry_after != null) retryAfter = body.retry_after;
      } catch {
        const text = await res.text().catch(() => "");
        if (text) detail = text;
      }

      // Append retry info to the detail message for display
      if (retryAfter != null && retryAfter > 0) {
        const mins = Math.floor(retryAfter / 60);
        const secs = retryAfter % 60;
        const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
        detail += ` (rate limited — retry after ${timeStr})`;
      }

      const err = new ApiError(detail, res.status);
      if (retryAfter != null) err.retryAfter = retryAfter;
      throw err;
    }

    // 204 No Content
    if (res.status === 204) return undefined as T;

    return res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Request timed out. The server took too long to respond.", 408);
    }
    throw new ApiError(
      err instanceof Error ? err.message : "Network request failed",
      0,
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

export const api = {
  // ── Projects ──────────────────────────────────────────────

  listProjects(): Promise<Project[]> {
    return request("/api/projects/");
  },

  getProject(id: string): Promise<ProjectDetail> {
    return request(`/api/projects/${id}`);
  },

  createProject(name: string, description = ""): Promise<ProjectDetail> {
    return request("/api/projects/", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  },

  updateProject(id: string, data: { name?: string; description?: string }): Promise<ProjectDetail> {
    return request(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  deleteProject(id: string): Promise<void> {
    return request(`/api/projects/${id}`, { method: "DELETE" });
  },

  // ── Sandbox / Files ───────────────────────────────────────

  getSandboxState(projectId: string): Promise<SandboxState> {
    return request(`/api/sandbox/${projectId}`);
  },

  upsertFile(projectId: string, path: string, content: string): Promise<ProjectFile> {
    return request(`/api/sandbox/${projectId}/files`, {
      method: "PUT",
      body: JSON.stringify({ path, content }),
    });
  },

  deleteFile(projectId: string, path: string): Promise<void> {
    return request(`/api/sandbox/${projectId}/files?path=${encodeURIComponent(path)}`, {
      method: "DELETE",
    });
  },

  // ── AI Generation ─────────────────────────────────────────

  generate(prompt: string, projectId?: string): Promise<GenerateResponse> {
    return request("/api/ai/generate", {
      method: "POST",
      body: JSON.stringify({ prompt, project_id: projectId }),
    });
  },

  // ── Chat ─────────────────────────────────────────────────

  getChatMessages(projectId: string): Promise<ChatMessageSchema[]> {
    return request(`/api/projects/${projectId}/chat`);
  },

  saveChatMessage(projectId: string, role: string, content: string, files?: ProjectFile[]): Promise<ChatMessageSchema> {
    return request(`/api/projects/${projectId}/chat`, {
      method: "POST",
      body: JSON.stringify({ role, content, files: files || [] }),
    });
  },

  // ── Figma URL import ────────────────────────────────────────

  importFigmaUrl(figmaUrl: string, accessToken: string): Promise<GenerateResponse> {
    return request("/api/figma/import-url", {
      method: "POST",
      body: JSON.stringify({ figma_url: figmaUrl, access_token: accessToken }),
    }, 300000); // 5 min timeout — Figma fetch + AI generation
  },

  // ── Health ────────────────────────────────────────────────

  health(): Promise<{ status: string; app: string }> {
    return request("/api/health");
  },
};
