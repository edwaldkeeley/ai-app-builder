"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "./components/Sidebar";
import MainContent from "./components/MainContent";
import FileExplorer from "./components/FileExplorer";
import { api } from "./lib/api";
import { useAuth } from "./contexts/AuthContext";
import { useProjects } from "./hooks/useProjects";
import { useChat } from "./hooks/useChat";
import { useFileSave } from "./hooks/useFileSave";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useToast } from "./components/Toast";

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
  const [showExplorer, setShowExplorer] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const [viewMode, setViewMode] = useState<"preview" | "code" | "split">("preview");
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const filesRef = useRef(files);
  const activeProjectIdRef = useRef(activeProjectId);

  // ── Effects (also hooks — must be before early returns) ──
  useEffect(() => {
    filesRef.current = files;
  }, [files]);
  useEffect(() => {
    activeProjectIdRef.current = activeProjectId;
  }, [activeProjectId]);

  // Load chat messages when a project is selected
  useEffect(() => {
    if (!activeProjectId) {
      clearChatMessages();
      return;
    }
    if (generating) return;
    loadChatMessages(activeProjectId);
  }, [activeProjectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Responsive: detect mobile width and auto-collapse panels
  useEffect(() => {
    const checkWidth = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) {
        setShowExplorer(false);
      }
    };
    checkWidth();
    window.addEventListener("resize", checkWidth);
    return () => window.removeEventListener("resize", checkWidth);
  }, []);

  // Global keyboard shortcuts
  useKeyboardShortcuts({
    onEscape: () => {
      setShowMobileSidebar(false);
    },
    onToggleSidebar: () => {
      if (isMobile) {
        setShowMobileSidebar((prev) => !prev);
      }
    },
    onToggleExplorer: () => {
      if (!isMobile) {
        setShowExplorer((prev) => !prev);
      }
    },
    onNewProject: () => {
      handleCreateProject();
    },
  });

  // Fetch project files when active project changes
  useEffect(() => {
    if (!activeProjectId) {
      setFiles([]);
      return;
    }
    api.getProject(activeProjectId).then((detail) => {
      setFiles(detail.files);
    }).catch((err) => {
      console.error("Failed to fetch project files:", err);
      showToast("error", "Failed to load project files");
      setError("Failed to load project files. Please try again.");
    });
  }, [activeProjectId]); // eslint-disable-line react-hooks/exhaustive-deps

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
    generate(prompt, projectId, filesRef.current, setFiles, fetchProjects, setError);
  }, [generating, handleNewProject, setChatMode, setFiles, fetchProjects, setError, generate]);

  const handleBackToProjects = useCallback(() => {
    setActiveProjectId(null);
    setChatMode(false);
  }, [setActiveProjectId, setChatMode]);

  const handleFigmaImportComplete = useCallback((projectId: string) => {
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
      <Sidebar
        projects={projects}
        activeProjectId={activeProjectId}
        onSelectProject={handleSelectProject}
        onNewProject={handleCreateProject}
        onDeleteProject={handleDeleteProject}
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
      />

      {/* File Explorer (only when a project is active and not in preview mode) */}
      {activeProject && viewMode !== "preview" && (
        <FileExplorer
          key={activeProjectId}
          files={files}
          activeFilePath={activeFilePath}
          onSelectFile={setActiveFilePath}
          onAddFile={handleAddFile}
          onDeleteFile={handleDeleteFile}
          onRenameFile={handleRenameFile}
          collapsed={isMobile ? false : !showExplorer}
          onToggleCollapse={() => setShowExplorer((prev) => !prev)}
          dirtyFiles={dirtyFiles}
          loading={loading}
          isMobile={isMobile}
        />
      )}

      {/* Mobile hamburger button */}
      {isMobile && !showMobileSidebar && (
        <button
          onClick={() => setShowMobileSidebar(true)}
          className="fixed top-3 left-3 z-30 p-2 rounded-lg bg-surface border border-border shadow-lg text-foreground hover:bg-sidebar transition-colors"
          aria-label="Open sidebar"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      )}

      <main className="flex-1 flex flex-col min-w-0">
        <MainContent
          loading={loading}
          error={error}
          activeProject={activeProject}
          files={files}
          onRetry={fetchProjects}
          onFilesChange={handleFilesChange}
          onSendPrompt={handlePrompt}
          generating={generating}
          onAddFile={handleAddFile}
          activeFilePath={activeFilePath}
          onActiveFileChange={setActiveFilePath}
          showExplorer={showExplorer}
          onToggleExplorer={() => setShowExplorer((prev) => !prev)}
          saveStatus={saveStatus}
          onFigmaImportComplete={handleFigmaImportComplete}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
        />
      </main>
    </div>
  );
}
