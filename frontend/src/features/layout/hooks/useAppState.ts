"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/app/lib/api";
import { useProjects } from "@/features/projects/hooks/useProjects";
import { useChat } from "@/features/chat/hooks/useChat";
import { useFileSave } from "@/features/editor/hooks/useFileSave";
import { useIsMobile } from "@/features/layout/hooks/useIsMobile";
import { useToast } from "@/components/ui/Toast";
import type { ProjectFile, Project, ChatMessage } from "@/app/lib/types";
import type { WritingStatus } from "@/features/chat/hooks/useChat";
import type { SaveStatus } from "@/features/editor/hooks/useFileSave";

export interface AppState {
  // From useProjects
  projects: Project[];
  activeProjectId: string | null;
  setActiveProjectId: (id: string | null) => void;
  activeProject: Project | null;
  loading: boolean;
  error: string | null;
  setError: (err: string | null) => void;
  creating: boolean;
  deleting: string | null;
  fetchProjects: () => void;
  handleDeleteProject: (id: string) => void;

  // From useChat
  chatMessages: ChatMessage[];
  generating: boolean;
  chatMode: boolean;
  setChatMode: (mode: boolean) => void;
  writingStatus: WritingStatus | null;
  clearChatMessages: () => void;

  // From useFileSave
  files: ProjectFile[];
  dirtyFiles: Set<string>;
  saveStatus: SaveStatus;
  handleFilesChange: (files: ProjectFile[]) => void;
  handleAddFile: (path: string) => void;
  handleDeleteFile: (path: string) => void;
  handleRenameFile: (oldPath: string, newPath: string) => void;

  // UI state
  activeFilePath: string | null;
  setActiveFilePath: (path: string | null) => void;
  isMobile: boolean;
  viewMode: "preview" | "code" | "split";
  setViewMode: (mode: "preview" | "code" | "split") => void;
  framework: "vanilla" | "react";
  showMobileSidebar: boolean;
  setShowMobileSidebar: (show: boolean) => void;
  filesLoading: boolean;

  // Orchestration callbacks
  handleSelectProject: (id: string) => void;
  handleCreateProject: () => void;
  handlePrompt: (prompt: string) => void;
  handleFrameworkChange: (framework: "vanilla" | "react") => void;
  handleBackToProjects: () => void;
  handleRenameProject: (id: string, name: string) => void;
  handleFigmaImportComplete: (projectId: string) => void;
  handleDesignUploadComplete: (projectId: string) => void;
  handleSave: () => void;
  handleCycleFiles: () => void;
  handleCycleFilesBackward: () => void;
}

/**
 * Orchestrator hook that composes all sub-hooks and UI state used by the home page.
 * Extracted to keep page.tsx lean and make the state flow testable in isolation.
 */
export function useAppState(): AppState {
  const { showToast } = useToast();
  const isMobile = useIsMobile();

  // ── Sub-hooks ────────────────────────────────────────────────
  const {
    projects,
    activeProjectId,
    setActiveProjectId,
    activeProject,
    loading,
    error,
    setError,
    creating,
    deleting,
    fetchProjects,
    handleNewProject,
    handleDeleteProject,
    handleSelectProject: selectProject,
  } = useProjects();

  const {
    chatMessages,
    generating,
    chatMode,
    setChatMode,
    writingStatus,
    loadChatMessages,
    clearChatMessages,
    handlePrompt: generate,
  } = useChat();

  const {
    files,
    setFiles,
    dirtyFiles,
    saveStatus,
    handleFilesChange,
    handleAddFile,
    handleDeleteFile,
    handleRenameFile,
  } = useFileSave(activeProjectId);

  // ── UI state ──────────────────────────────────────────────────
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"preview" | "code" | "split">("preview");
  const [framework, setFramework] = useState<"vanilla" | "react">(activeProject?.framework ?? "vanilla");
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const [filesLoading, setFilesLoading] = useState(false);

  // Refs for use in callbacks (avoid stale closures)
  const filesRef = useRef(files);
  const activeProjectIdRef = useRef(activeProjectId);
  const activeFilePathRef = useRef(activeFilePath);
  const dirtyFilesRef = useRef(dirtyFiles);

  useEffect(() => { filesRef.current = files; }, [files]);
  useEffect(() => { activeProjectIdRef.current = activeProjectId; }, [activeProjectId]);
  useEffect(() => { activeFilePathRef.current = activeFilePath; }, [activeFilePath]);
  useEffect(() => { dirtyFilesRef.current = dirtyFiles; }, [dirtyFiles]);

  // Auto-collapse mobile sidebar on mobile resize
  useEffect(() => {
    if (isMobile) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShowMobileSidebar(false);
    }
  }, [isMobile]);

  // Load chat messages when a project is selected
  useEffect(() => {
    if (!activeProjectId) {
      clearChatMessages();
      return;
    }
    if (generating) return;
    loadChatMessages(activeProjectId);
  }, [activeProjectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync framework toggle from the active project
  useEffect(() => {
    if (activeProject) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFramework(activeProject.framework);
    }
  }, [activeProject, activeProject?.framework]);

  // Warn before leaving with unsaved changes
  useEffect(() => {
    if (dirtyFiles.size === 0) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirtyFiles.size]);

  // Fetch project files when active project changes
  useEffect(() => {
    if (!activeProjectId) {
      setFiles([]);
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFilesLoading(true);
    api.getProject(activeProjectId).then((detail) => {
      setFiles(detail.files);
    }).catch((err) => {
      console.error("Failed to fetch project files:", err);
      showToast("error", "Failed to load project files");
      setError("Failed to load project files. Please try again.");
    }).finally(() => {
      setFilesLoading(false);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProjectId]);

  // ── Orchestration callbacks ───────────────────────────────────

  const handleSelectProject = useCallback((id: string) => {
    selectProject(id);
    setChatMode(true);
  }, [selectProject, setChatMode]);

  const handleCreateProject = useCallback(async () => {
    const project = await handleNewProject();
    if (project) {
      setChatMode(true);
      setFiles(project.files);
    }
  }, [handleNewProject, setChatMode, setFiles]);

  const handlePrompt = useCallback(async (prompt: string) => {
    if (generating) return;

    let projectId = activeProjectIdRef.current;
    if (!projectId) {
      const project = await handleNewProject();
      if (!project) return;
      projectId = project.id;
      setChatMode(true);
    }

    if (!projectId) return;
    generate(prompt, projectId, filesRef.current, setFiles, fetchProjects, setError, framework);
  }, [generating, handleNewProject, setChatMode, setFiles, fetchProjects, setError, generate, framework]);

  const handleFrameworkChange = useCallback((newFramework: "vanilla" | "react") => {
    setFramework(newFramework);
    const pid = activeProjectIdRef.current;
    if (pid) {
      api.updateProject(pid, { framework: newFramework }).catch(() => {});
    }
  }, []);

  const handleBackToProjects = useCallback(() => {
    setActiveProjectId(null);
    setChatMode(false);
  }, [setActiveProjectId, setChatMode]);

  const handleRenameProject = useCallback(async (id: string, name: string) => {
    try {
      await api.updateProject(id, { name });
      fetchProjects();
      showToast("success", `Renamed to "${name}"`);
    } catch {
      showToast("error", "Failed to rename project");
    }
  }, [fetchProjects, showToast]);

  const handleFigmaImportComplete = useCallback((projectId: string) => {
    fetchProjects();
    selectProject(projectId);
    setChatMode(true);
  }, [fetchProjects, selectProject, setChatMode]);

  const handleDesignUploadComplete = useCallback((projectId: string) => {
    fetchProjects();
    selectProject(projectId);
    setChatMode(true);
  }, [fetchProjects, selectProject, setChatMode]);

  // Keyboard shortcut callbacks (washed through refs inside useAppState)
  // These are used only inside page.tsx via useKeyboardShortcuts
  const handleSave = useCallback(async () => {
    const currentDirty = dirtyFilesRef.current;
    if (!activeProjectIdRef.current || currentDirty.size === 0) return;
    for (const path of currentDirty) {
      const file = filesRef.current.find((f) => f.path === path);
      if (file) {
        try {
          await api.upsertFile(activeProjectIdRef.current, path, file.content);
        } catch {
          showToast("error", `Failed to save ${path}`);
        }
      }
    }
    showToast("success", "All files saved");
  }, [showToast]);

  const handleCycleFiles = useCallback(() => {
    const currentFiles = filesRef.current;
    if (currentFiles.length === 0) return;
    const currentIndex = currentFiles.findIndex((f) => f.path === activeFilePathRef.current);
    const nextIndex = (currentIndex + 1) % currentFiles.length;
    setActiveFilePath(currentFiles[nextIndex].path);
  }, []);

  const handleCycleFilesBackward = useCallback(() => {
    const currentFiles = filesRef.current;
    if (currentFiles.length === 0) return;
    const currentIndex = currentFiles.findIndex((f) => f.path === activeFilePathRef.current);
    const prevIndex = (currentIndex - 1 + currentFiles.length) % currentFiles.length;
    setActiveFilePath(currentFiles[prevIndex].path);
  }, []);

  return {
    // Projects
    projects,
    activeProjectId,
    setActiveProjectId,
    activeProject,
    loading,
    error,
    setError,
    creating,
    deleting,
    fetchProjects,
    handleDeleteProject,

    // Chat
    chatMessages,
    generating,
    chatMode,
    setChatMode,
    writingStatus,
    clearChatMessages,

    // Files
    files,
    dirtyFiles,
    saveStatus,
    handleFilesChange,
    handleAddFile,
    handleDeleteFile,
    handleRenameFile,

    // UI state
    activeFilePath,
    setActiveFilePath,
    isMobile,
    viewMode,
    setViewMode,
    framework,
    showMobileSidebar,
    setShowMobileSidebar,
    filesLoading,

    // Callbacks
    handleSelectProject,
    handleCreateProject,
    handlePrompt,
    handleFrameworkChange,
    handleBackToProjects,
    handleRenameProject,
    handleFigmaImportComplete,
    handleDesignUploadComplete,

    // Keyboard shortcut helpers (exposed for page.tsx to wire up)
    handleSave,
    handleCycleFiles,
    handleCycleFilesBackward,
  };
}
