import type { ChatMessageSchema, FigmaFile, FigmaImportResponse, FigmaStatus, GenerateResponse, Project, ProjectDetail, ProjectFile, SandboxState } from "./types";

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
  onError?: (detail: string) => void;
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
            callbacks.onError?.(msg.detail);
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
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(text || `Request failed: ${res.status}`, res.status);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json();
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

  // ── Figma ─────────────────────────────────────────────────

  getFigmaAuthUrl(): Promise<{ url: string }> {
    return request("/api/figma/auth-url");
  },

  getFigmaStatus(): Promise<FigmaStatus> {
    return request("/api/figma/status");
  },

  listFigmaFiles(): Promise<{ files: FigmaFile[] }> {
    return request("/api/figma/files");
  },

  importFigmaFile(fileKey: string): Promise<FigmaImportResponse> {
    return request("/api/figma/import", {
      method: "POST",
      body: JSON.stringify({ figma_file_key: fileKey }),
    });
  },

  // ── Health ────────────────────────────────────────────────

  health(): Promise<{ status: string; app: string }> {
    return request("/api/health");
  },
};
