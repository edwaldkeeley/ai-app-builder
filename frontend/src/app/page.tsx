"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { api } from "./lib/api";
import { useAuth } from "@/app/(auth)/contexts/AuthContext";
import { useProjects } from "@/features/projects/hooks/useProjects";
import { useChat } from "@/features/chat/hooks/useChat";
import { useFileSave } from "@/features/editor/hooks/useFileSave";
import { useKeyboardShortcuts } from "@/features/layout/hooks/useKeyboardShortcuts";
import { useToast } from "@/components/ui/Toast";
import { SkeletonSidebar, SkeletonEditor } from "@/components/ui/Skeleton";

// Dynamic imports for heavy components — loaded only when needed
const Sidebar = dynamic(() => import("@/features/layout/components/Sidebar"), { ssr: false });
const MainContent = dynamic(() => import("@/features/layout/components/MainContent"), { ssr: false });

export default function Home() {
  const { showToast } = useToast();
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  // ── All hooks MUST be called unconditionally (before any early return) ──
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

  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [viewMode, setViewMode] = useState<"preview" | "code" | "split">("preview");
  const [framework, setFramework] = useState<"vanilla" | "react">(activeProject?.framework ?? "vanilla");
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const [filesLoading, setFilesLoading] = useState(false);
  const filesRef = useRef(files);
  const activeProjectIdRef = useRef(activeProjectId);
  const activeFilePathRef = useRef(activeFilePath);
  const dirtyFilesRef = useRef(dirtyFiles);

  // ── Effects (also hooks — must be before early returns) ──
  useEffect(() => {
    filesRef.current = files;
  }, [files]);
  useEffect(() => {
    activeProjectIdRef.current = activeProjectId;
  }, [activeProjectId]);
  useEffect(() => {
    activeFilePathRef.current = activeFilePath;
  }, [activeFilePath]);
  useEffect(() => {
    dirtyFilesRef.current = dirtyFiles;
  }, [dirtyFiles]);

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

  // Responsive: detect mobile width and auto-collapse panels
  useEffect(() => {
    const checkWidth = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) {
        setShowMobileSidebar(false);
      }
    };
    checkWidth();
    window.addEventListener("resize", checkWidth);
    return () => window.removeEventListener("resize", checkWidth);
  }, []);

  // Warn before leaving with unsaved changes
  useEffect(() => {
    if (dirtyFiles.size === 0) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirtyFiles.size]);

  // Ctrl+S — save all dirty files immediately
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

  // Ctrl+Tab — cycle through files
  const handleCycleFiles = useCallback(() => {
    const currentFiles = filesRef.current;
    if (currentFiles.length === 0) return;
    const currentIndex = currentFiles.findIndex((f) => f.path === activeFilePathRef.current);
    const nextIndex = (currentIndex + 1) % currentFiles.length;
    setActiveFilePath(currentFiles[nextIndex].path);
  }, []);

  // Ctrl+PageUp — cycle backward through files
  const handleCycleFilesBackward = useCallback(() => {
    const currentFiles = filesRef.current;
    if (currentFiles.length === 0) return;
    const currentIndex = currentFiles.findIndex((f) => f.path === activeFilePathRef.current);
    const prevIndex = (currentIndex - 1 + currentFiles.length) % currentFiles.length;
    setActiveFilePath(currentFiles[prevIndex].path);
  }, []);

  // Global keyboard shortcuts
  useKeyboardShortcuts({
    onSave: handleSave,
    onEscape: () => {
      setShowMobileSidebar(false);
    },
    onToggleSidebar: () => {
      if (isMobile) {
        setShowMobileSidebar((prev) => !prev);
      }
    },
    onToggleViewMode: () => {
      setViewMode((prev) => prev === "preview" ? "code" : prev === "code" ? "split" : "preview");
    },
    onNewProject: () => {
      handleCreateProject();
    },
    onCycleFiles: handleCycleFiles,
    onCycleFilesBackward: handleCycleFilesBackward,
  });

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

  // ── Callbacks (also hooks — must be before early returns) ──
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
    // If a project is active, update its framework on the backend
    const pid = activeProjectIdRef.current;
    if (pid) {
      api.updateProject(pid, { framework: newFramework }).catch(() => {
        // Silently fail — the toggle will reset on next project load
      });
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

  // Auth guard — redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  if (authLoading) {
    return (
      <div className="h-dvh flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-text-secondary">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null; // Will redirect to /login
  }

  return (
    <div className="h-dvh flex">
      <Suspense fallback={<SkeletonSidebar />}>
        <Sidebar
          projects={projects}
          activeProjectId={activeProjectId}
          onSelectProject={handleSelectProject}
          onNewProject={handleCreateProject}
          onDeleteProject={handleDeleteProject}
          onRenameProject={handleRenameProject}
          creating={creating}
          deleting={deleting}
          chatMode={chatMode}
          chatMessages={chatMessages}
          generating={generating}
          writingStatus={writingStatus}
          onSendPrompt={handlePrompt}
          onBackToProjects={handleBackToProjects}
          loading={loading}
          isMobile={isMobile}
          showMobileSidebar={showMobileSidebar}
          onCloseMobileSidebar={() => setShowMobileSidebar(false)}
          onFigmaImportComplete={handleFigmaImportComplete}
          onDesignUploadComplete={handleDesignUploadComplete}
        />
      </Suspense>

      {/* Mobile hamburger button */}
      {isMobile && !showMobileSidebar && (
        <button
          onClick={() => setShowMobileSidebar(true)}
          className="fixed top-3 left-3 z-30 p-2 rounded-lg bg-surface border border-border shadow-lg text-foreground hover:bg-sidebar transition-colors touch-target"
          style={{ top: "calc(12px + env(safe-area-inset-top, 0px))" }}
          aria-label="Open sidebar"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      )}

      <main className="flex-1 flex flex-col min-w-0">
        <Suspense fallback={<SkeletonEditor />}>
          <MainContent
            loading={loading || filesLoading}
            error={error}
            activeProject={activeProject}
            files={files}
            onRetry={fetchProjects}
            onFilesChange={handleFilesChange}
            onSendPrompt={handlePrompt}
            generating={generating}
            onAddFile={handleAddFile}
            onDeleteFile={handleDeleteFile}
            onRenameFile={handleRenameFile}
            activeFilePath={activeFilePath}
            onActiveFileChange={setActiveFilePath}
            saveStatus={saveStatus}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onFigmaImportComplete={handleFigmaImportComplete}
            onDesignUploadComplete={handleDesignUploadComplete}
            isMobile={isMobile}
            dirtyFiles={dirtyFiles}
            framework={framework}
            onFrameworkChange={handleFrameworkChange}
          />
        </Suspense>
      </main>
    </div>
  );
}
