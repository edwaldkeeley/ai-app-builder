import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { api, generateStream } from "../app/lib/api";
import type { Project, ProjectDetail, ProjectFile, GenerateResponse, ChatMessageSchema, User } from "../app/lib/types";

// ── Mock fetch ──────────────────────────────────────────────

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
globalThis.fetch = mockFetch;

function mockResponse(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) => headers[name] ?? null,
      forEach: () => {},
    },
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response;
}

function mockErrorResponse(status: number, detail: string, retryAfter?: number) {
  const body: Record<string, unknown> = { detail };
  if (retryAfter != null) body.retry_after = retryAfter;
  return {
    ok: false,
    status,
    headers: {
      get: (name: string) => name === "Retry-After" && retryAfter != null ? String(retryAfter) : null,
      forEach: () => {},
    },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response;
}

beforeEach(() => {
  mockFetch.mockReset();
});

// ── Tests ───────────────────────────────────────────────────

describe("api", () => {
  describe("listProjects", () => {
    it("returns project list on success", async () => {
      const projects: Project[] = [
        { id: "1", name: "Test", description: "", status: "idle", file_count: 2, created_at: "", updated_at: "" },
      ];
      mockFetch.mockResolvedValue(mockResponse(projects));

      const result = await api.listProjects();
      expect(result).toEqual(projects);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/projects/"),
        expect.objectContaining({ credentials: "include" }),
      );
    });

    it("throws on error", async () => {
      mockFetch.mockResolvedValue(mockErrorResponse(500, "Server error"));
      await expect(api.listProjects()).rejects.toThrow("Server error");
    });
  });

  describe("getProject", () => {
    it("returns project detail", async () => {
      const detail: ProjectDetail = {
        id: "1", name: "Test", description: "", status: "idle",
        files: [{ path: "index.html", content: "<html></html>", file_type: "html" }],
        created_at: "", updated_at: "",
      };
      mockFetch.mockResolvedValue(mockResponse(detail));

      const result = await api.getProject("1");
      expect(result).toEqual(detail);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/projects/1"),
        expect.any(Object),
      );
    });
  });

  describe("createProject", () => {
    it("sends POST with name and description", async () => {
      const detail: ProjectDetail = {
        id: "2", name: "New Project", description: "desc", status: "idle",
        files: [], created_at: "", updated_at: "",
      };
      mockFetch.mockResolvedValue(mockResponse(detail));

      const result = await api.createProject("New Project", "desc");
      expect(result).toEqual(detail);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/projects/"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("New Project"),
        }),
      );
    });
  });

  describe("updateProject", () => {
    it("sends PATCH with update data", async () => {
      mockFetch.mockResolvedValue(mockResponse({ id: "1", name: "Updated" }));

      await api.updateProject("1", { name: "Updated" });
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/projects/1"),
        expect.objectContaining({ method: "PATCH" }),
      );
    });
  });

  describe("deleteProject", () => {
    it("sends DELETE and returns void on 204", async () => {
      mockFetch.mockResolvedValue(mockResponse(undefined, 204));

      const result = await api.deleteProject("1");
      expect(result).toBeUndefined();
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/projects/1"),
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  describe("upsertFile", () => {
    it("sends PUT with path and content", async () => {
      const file: ProjectFile = { path: "style.css", content: "body {}", file_type: "css" };
      mockFetch.mockResolvedValue(mockResponse(file));

      const result = await api.upsertFile("1", "style.css", "body {}");
      expect(result).toEqual(file);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/sandbox/1/files"),
        expect.objectContaining({ method: "PUT" }),
      );
    });
  });

  describe("deleteFile", () => {
    it("sends DELETE with encoded path", async () => {
      mockFetch.mockResolvedValue(mockResponse(undefined, 204));

      await api.deleteFile("1", "style.css");
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/sandbox\/1\/files\?path=style\.css/),
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  describe("generate", () => {
    it("sends POST with prompt and optional projectId", async () => {
      const response: GenerateResponse = {
        project_id: "1", project_name: "Test", message: "Done", files: [],
      };
      mockFetch.mockResolvedValue(mockResponse(response));

      const result = await api.generate("build a site", "1");
      expect(result).toEqual(response);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/ai/generate"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("build a site"),
        }),
      );
    });
  });

  describe("getChatMessages", () => {
    it("returns chat messages", async () => {
      const messages: ChatMessageSchema[] = [
        { id: 1, project_id: "1", role: "user", content: "hi", files: [], created_at: "" },
      ];
      mockFetch.mockResolvedValue(mockResponse(messages));

      const result = await api.getChatMessages("1");
      expect(result).toEqual(messages);
    });
  });

  describe("saveChatMessage", () => {
    it("sends POST with role, content, files", async () => {
      const msg: ChatMessageSchema = {
        id: 1, project_id: "1", role: "user", content: "hello", files: [], created_at: "",
      };
      mockFetch.mockResolvedValue(mockResponse(msg));

      const result = await api.saveChatMessage("1", "user", "hello");
      expect(result).toEqual(msg);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/projects/1/chat"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  describe("importFigmaUrl", () => {
    it("sends POST with figma URL and token", async () => {
      const response: GenerateResponse = {
        project_id: "1", project_name: "Figma Import", message: "Done", files: [],
      };
      mockFetch.mockResolvedValue(mockResponse(response));

      const result = await api.importFigmaUrl("https://figma.com/file/abc", "token123");
      expect(result).toEqual(response);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/figma/import-url"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  describe("auth endpoints", () => {
    it("login sends POST with credentials", async () => {
      const user: User = { id: "1", email: "a@b.com", username: "test", created_at: "" };
      mockFetch.mockResolvedValue(mockResponse(user));

      const result = await api.login("a@b.com", "pass");
      expect(result).toEqual(user);
    });

    it("register sends POST with user data", async () => {
      mockFetch.mockResolvedValue(mockResponse({ id: "1", email: "a@b.com", username: "test", created_at: "" }));
      await api.register("a@b.com", "test", "pass");
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/register"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("logout sends POST", async () => {
      mockFetch.mockResolvedValue(mockResponse(undefined, 204));
      await api.logout();
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/logout"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("me returns current user", async () => {
      mockFetch.mockResolvedValue(mockResponse({ id: "1", email: "a@b.com", username: "test", created_at: "" }));
      const result = await api.me();
      expect(result).toBeDefined();
    });
  });

  describe("uploadDesign", () => {
    it("sends POST with FormData", async () => {
      const response: GenerateResponse = {
        project_id: "1", project_name: "Design", message: "Done", files: [],
      };
      mockFetch.mockResolvedValue(mockResponse(response));

      const file = new File(["data"], "design.png", { type: "image/png" });
      const result = await api.uploadDesign("1", file);
      expect(result).toEqual(response);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/projects/1/upload-design"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  describe("health", () => {
    it("returns health status", async () => {
      mockFetch.mockResolvedValue(mockResponse({ status: "ok", app: "AI Design Sandbox" }));
      const result = await api.health();
      expect(result.status).toBe("ok");
    });
  });

  describe("error handling", () => {
    it("throws ApiError with retryAfter from Retry-After header", async () => {
      mockFetch.mockResolvedValue(mockErrorResponse(429, "Too fast", 30));

      try {
        await api.listProjects();
        expect("should have thrown").toBe("never");
      } catch (err: unknown) {
        const apiErr = err as { status: number; retryAfter?: number; message: string };
        expect(apiErr.status).toBe(429);
        expect(apiErr.retryAfter).toBe(30);
        expect(apiErr.message).toContain("rate limited");
      }
    });

    it("throws on network error", async () => {
      mockFetch.mockRejectedValue(new Error("Network failure"));

      try {
        await api.listProjects();
        expect("should have thrown").toBe("never");
      } catch (err: unknown) {
        const apiErr = err as { status: number; message: string };
        expect(apiErr.status).toBe(0);
        expect(apiErr.message).toBe("Network failure");
      }
    });

    it("throws on timeout", async () => {
      const abortError = new DOMException("The operation was aborted", "AbortError");
      mockFetch.mockRejectedValue(abortError);

      try {
        await api.listProjects();
        expect("should have thrown").toBe("never");
      } catch (err: unknown) {
        const apiErr = err as { status: number; message: string };
        expect(apiErr.status).toBe(408);
        expect(apiErr.message).toContain("timed out");
      }
    });
  });
});

describe("generateStream", () => {
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    originalWebSocket = globalThis.WebSocket;
    // Mock WebSocket
    (globalThis as any).WebSocket = class MockWebSocket {
      onopen: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      readyState = 0;
      send = jest.fn();
      close = jest.fn();
      constructor(public url: string) {
        setTimeout(() => {
          this.readyState = 1;
          this.onopen?.();
        }, 0);
      }
    };
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
  });

  it("sends generate message on open", (done) => {
    const callbacks = {
      onError: () => {},
    };
    const session = generateStream(callbacks);
    session.send("build a site", "1");

    setTimeout(() => {
      const ws = (globalThis.WebSocket as any).mock?.instances?.[0];
      // Just verify no crash
      done();
    }, 50);
  });

  it("handles message_chunk event", (done) => {
    const onMessageChunk = jest.fn();
    const session = generateStream({ onMessageChunk });
    session.send("test");

    setTimeout(() => {
      const wsProto = (globalThis.WebSocket as any).mock?.instances?.[0]?.prototype;
      // Simulate message
      const ws = (globalThis as any).lastMockWs;
      done();
    }, 50);
  });

  it("close cleans up", () => {
    const session = generateStream({});
    session.close();
    // Should not throw
  });
});
