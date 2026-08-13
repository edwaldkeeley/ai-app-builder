import type { ChatMessageSchema, GenerateResponse, Project, ProjectDetail, ProjectFile, SandboxState, User } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Re-export WebSocket stream types and factory from dedicated module for backward compatibility
export type { StreamCallbacks, StreamSession } from "./ws";
export { generateStream } from "./ws";

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

async function request<T>(path: string, options?: RequestInit, timeoutMs = 600000): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      credentials: "include",
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

// ── Simple in-memory cache ──────────────────────────────────
// Reduces redundant network requests for data that changes infrequently.
// Cache entries expire after CACHE_TTL_MS milliseconds.

const CACHE_TTL_MS = 30_000; // 30 seconds
const cache = new Map<string, { data: unknown; timestamp: number }>();

function getCached<T>(key: string): T | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
    cache.delete(key);
    return null;
  }
  return entry.data as T;
}

function setCache(key: string, data: unknown): void {
  cache.set(key, { data, timestamp: Date.now() });
}

function invalidateCache(prefix?: string): void {
  if (prefix) {
    for (const key of cache.keys()) {
      if (key.startsWith(prefix)) cache.delete(key);
    }
  } else {
    cache.clear();
  }
}

/** Clear all cached data (used in tests). */
export function clearApiCache(): void {
  cache.clear();
}

/** Wrapper that caches GET responses and invalidates on mutations. */
function withCache<T>(cacheKey: string, fetcher: () => Promise<T>): Promise<T> {
  const cached = getCached<T>(cacheKey);
  if (cached) return Promise.resolve(cached);
  return fetcher().then((data) => {
    setCache(cacheKey, data);
    return data;
  });
}

export const api = {
  // ── Projects ──────────────────────────────────────────────

  listProjects(): Promise<Project[]> {
    return withCache("projects", () => request<Project[]>("/api/projects/"));
  },

  getProject(id: string): Promise<ProjectDetail> {
    return withCache(`project:${id}`, () => request<ProjectDetail>(`/api/projects/${id}`));
  },

  createProject(name: string, description = ""): Promise<ProjectDetail> {
    invalidateCache("projects");
    return request("/api/projects/", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  },

  updateProject(id: string, data: { name?: string; description?: string; framework?: string }): Promise<ProjectDetail> {
    invalidateCache(`project:${id}`);
    invalidateCache("projects");
    return request(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  deleteProject(id: string): Promise<void> {
    invalidateCache(`project:${id}`);
    invalidateCache("projects");
    return request(`/api/projects/${id}`, { method: "DELETE" });
  },

  // ── Sandbox / Files ───────────────────────────────────────

  getSandboxState(projectId: string): Promise<SandboxState> {
    return request(`/api/sandbox/${projectId}`);
  },

  upsertFile(projectId: string, path: string, content: string): Promise<ProjectFile> {
    invalidateCache(`project:${projectId}`);
    return request(`/api/sandbox/${projectId}/files`, {
      method: "PUT",
      body: JSON.stringify({ path, content }),
    });
  },

  deleteFile(projectId: string, path: string): Promise<void> {
    invalidateCache(`project:${projectId}`);
    return request(`/api/sandbox/${projectId}/files?path=${encodeURIComponent(path)}`, {
      method: "DELETE",
    });
  },

  // ── AI Generation ─────────────────────────────────────────

  generate(prompt: string, projectId?: string, framework?: string): Promise<GenerateResponse> {
    if (projectId) invalidateCache(`project:${projectId}`);
    invalidateCache("projects");
    return request("/api/ai/generate", {
      method: "POST",
      body: JSON.stringify({ prompt, project_id: projectId, framework: framework || "vanilla" }),
    });
  },

  // ── Chat ─────────────────────────────────────────────────

  getChatMessages(projectId: string): Promise<ChatMessageSchema[]> {
    return withCache(`chat:${projectId}`, () => request<ChatMessageSchema[]>(`/api/projects/${projectId}/chat`));
  },

  saveChatMessage(projectId: string, role: string, content: string, files?: ProjectFile[]): Promise<ChatMessageSchema> {
    invalidateCache(`chat:${projectId}`);
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
    }, 600000); // 10 min timeout — Figma fetch + AI generation
  },

  // ── Auth ──────────────────────────────────────────────────

  login(email: string, password: string): Promise<User> {
    return request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  register(email: string, username: string, password: string): Promise<User> {
    return request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, username, password }),
    });
  },

  logout(): Promise<void> {
    return request("/api/auth/logout", { method: "POST" });
  },

  me(): Promise<User> {
    return request("/api/auth/me");
  },

  updateUser(data: { username?: string; email?: string }): Promise<User> {
    return request("/api/auth/me", {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    return request("/api/auth/me/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
  },

  deleteAccount(): Promise<void> {
    return request("/api/auth/me", { method: "DELETE" });
  },

  // ── Design Upload ──────────────────────────────────────────

  async uploadDesign(
    projectId: string,
    file: File,
    prompt?: string,
    signal?: AbortSignal,
  ): Promise<GenerateResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (prompt) formData.append("prompt", prompt);

    const res = await fetch(`${BASE}/api/projects/${projectId}/upload-design`, {
      method: "POST",
      credentials: "include",
      body: formData,
      signal,
    });

    if (!res.ok) {
      let detail = `Upload failed: ${res.status}`;
      try {
        const body = await res.json();
        if (body?.detail) {
          detail = typeof body.detail === "object" ? body.detail.message ?? String(body.detail) : body.detail;
        }
      } catch {
        // ignore
      }
      throw new ApiError(detail, res.status);
    }

    return res.json();
  },

  // ── Health ────────────────────────────────────────────────

  health(): Promise<{ status: string; app: string }> {
    return request("/api/health");
  },
};
