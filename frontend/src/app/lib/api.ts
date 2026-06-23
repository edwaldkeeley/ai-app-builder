import type { ChatMessageSchema, GenerateResponse, Project, ProjectDetail, ProjectFile, SandboxState } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  // ── Health ────────────────────────────────────────────────

  health(): Promise<{ status: string; app: string }> {
    return request("/api/health");
  },
};
