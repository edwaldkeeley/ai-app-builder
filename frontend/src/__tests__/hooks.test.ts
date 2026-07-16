import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useProjects } from "../app/hooks/useProjects";
import { useFileSave } from "../app/hooks/useFileSave";
import { api } from "../app/lib/api";
import type { Project, ProjectDetail, ProjectFile } from "../app/lib/types";

// ── Mock dependencies ──────────────────────────────────────

jest.mock("../app/lib/api", () => ({
  api: {
    listProjects: jest.fn(),
    createProject: jest.fn(),
    deleteProject: jest.fn(),
    upsertFile: jest.fn(),
    deleteFile: jest.fn(),
  },
}));

jest.mock("../app/components/Toast", () => ({
  useToast: () => ({ showToast: jest.fn() }),
}));

const mockApi = api as jest.Mocked<typeof api>;

// ── Test data ──────────────────────────────────────────────

const mockProjects: Project[] = [
  { id: "1", name: "Project 1", description: "", status: "idle", file_count: 2, created_at: "2026-01-01", updated_at: "2026-01-01" },
  { id: "2", name: "Project 2", description: "", status: "idle", file_count: 1, created_at: "2026-01-02", updated_at: "2026-01-02" },
];

const mockProjectDetail: ProjectDetail = {
  id: "3", name: "New Project", description: "", status: "idle",
  files: [{ path: "index.html", content: "<html></html>", file_type: "html" }],
  created_at: "2026-01-03", updated_at: "2026-01-03",
};

// ── useProjects tests ──────────────────────────────────────

describe("useProjects", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (mockApi.listProjects as jest.Mock).mockResolvedValue(mockProjects);
  });

  it("loads projects on mount", async () => {
    const { result } = renderHook(() => useProjects());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projects).toEqual(mockProjects);
    expect(mockApi.listProjects).toHaveBeenCalledTimes(1);
  });

  it("sets error on fetch failure", async () => {
    (mockApi.listProjects as jest.Mock).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useProjects());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Network error");
    expect(result.current.projects).toEqual([]);
  });

  it("creates a new project", async () => {
    (mockApi.createProject as jest.Mock).mockResolvedValue(mockProjectDetail);
    const { result } = renderHook(() => useProjects());

    await waitFor(() => expect(result.current.loading).toBe(false));

    let project: ProjectDetail | null = null;
    await act(async () => {
      project = await result.current.handleNewProject();
    });

    expect(project).toEqual(mockProjectDetail);
    expect(mockApi.createProject).toHaveBeenCalledWith(expect.stringContaining("Project"));
    expect(result.current.activeProjectId).toBe("3");
  });

  it("deletes a project", async () => {
    (mockApi.deleteProject as jest.Mock).mockResolvedValue(undefined);
    const { result } = renderHook(() => useProjects());

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleDeleteProject("1");
    });

    expect(mockApi.deleteProject).toHaveBeenCalledWith("1");
    expect(result.current.projects).toHaveLength(1);
    expect(result.current.projects[0].id).toBe("2");
  });

  it("selects a project", () => {
    const { result } = renderHook(() => useProjects());

    act(() => {
      result.current.handleSelectProject("1");
    });

    expect(result.current.activeProjectId).toBe("1");
  });

  it("returns null activeProject when no project selected", () => {
    const { result } = renderHook(() => useProjects());
    expect(result.current.activeProject).toBeNull();
  });
});

// ── useFileSave tests ──────────────────────────────────────

describe("useFileSave", () => {
  const mockFile: ProjectFile = { path: "index.html", content: "<html></html>", file_type: "html" };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("initializes with empty files", () => {
    const { result } = renderHook(() => useFileSave("1"));
    expect(result.current.files).toEqual([]);
    expect(result.current.dirtyFiles.size).toBe(0);
    expect(result.current.saveStatus).toBe("idle");
  });

  it("adds a file", async () => {
    (mockApi.upsertFile as jest.Mock).mockResolvedValue(mockFile);
    const { result } = renderHook(() => useFileSave("1"));

    await act(async () => {
      await result.current.handleAddFile("index.html");
    });

    expect(mockApi.upsertFile).toHaveBeenCalledWith("1", "index.html", "");
    expect(result.current.files).toHaveLength(1);
    expect(result.current.files[0].path).toBe("index.html");
  });

  it("deletes a file", async () => {
    (mockApi.upsertFile as jest.Mock).mockResolvedValue(mockFile);
    (mockApi.deleteFile as jest.Mock).mockResolvedValue(undefined);
    const { result } = renderHook(() => useFileSave("1"));

    // First add a file
    await act(async () => {
      await result.current.handleAddFile("index.html");
    });

    // Then delete it
    await act(async () => {
      await result.current.handleDeleteFile("index.html");
    });

    expect(mockApi.deleteFile).toHaveBeenCalledWith("1", "index.html");
    expect(result.current.files).toHaveLength(0);
  });

  it("marks files as dirty on change", () => {
    const { result } = renderHook(() => useFileSave("1"));

    act(() => {
      result.current.handleFilesChange([mockFile]);
    });

    expect(result.current.files).toHaveLength(1);
    expect(result.current.dirtyFiles.has("index.html")).toBe(true);
  });

  it("renames a file", async () => {
    (mockApi.upsertFile as jest.Mock).mockResolvedValue(mockFile);
    (mockApi.deleteFile as jest.Mock).mockResolvedValue(undefined);
    const { result } = renderHook(() => useFileSave("1"));

    // Add a file first
    await act(async () => {
      await result.current.handleAddFile("index.html");
    });

    // Rename it
    await act(async () => {
      await result.current.handleRenameFile("index.html", "home.html");
    });

    expect(result.current.files[0].path).toBe("home.html");
  });

  it("clears dirty files when project changes", () => {
    const { result } = renderHook(() => useFileSave("1"));

    act(() => {
      result.current.handleFilesChange([mockFile]);
    });

    expect(result.current.dirtyFiles.size).toBeGreaterThan(0);

    // Re-render with different project ID
    const { result: result2 } = renderHook(() => useFileSave("2"));

    expect(result2.current.dirtyFiles.size).toBe(0);
  });
});
