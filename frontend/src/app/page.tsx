"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "./components/Sidebar";
import MainContent from "./components/MainContent";
import FileExplorer from "./components/FileExplorer";
import { api } from "./lib/api";
import { useProjects } from "./hooks/useProjects";
import { useChat } from "./hooks/useChat";
import { useFileSave } from "./hooks/useFileSave";

export default function Home() {
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
    handleFilesChange,
    handleAddFile,
    handleDeleteFile,
    handleRenameFile,
  } = useFileSave(activeProjectId);

  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [showExplorer, setShowExplorer] = useState(true);
  const filesRef = useRef(files);
  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  // Load chat messages when a project is selected
  // NOTE: generating is intentionally excluded from deps — including it would
  // cause the effect to re-fetch messages when generation finishes, overwriting
  // the in-memory streaming state with stale backend data.
  useEffect(() => {
    if (!activeProjectId) {
      clearChatMessages();
      return;
    }
    if (generating) return;
    loadChatMessages(activeProjectId);
  }, [activeProjectId]); // eslint-disable-line react-hooks/exhaustive-deps

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
      setError("Failed to load project files. Please try again.");
    });
  }, [activeProjectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Wrap handleSelectProject to also set chat mode
  const handleSelectProject = useCallback((id: string) => {
    selectProject(id);
    setChatMode(true);
  }, [selectProject, setChatMode]);

  // Wrap handleNewProject to also set chat mode
  const handleCreateProject = useCallback(async () => {
    const project = await handleNewProject();
    if (project) {
      setChatMode(true);
      setFiles(project.files);
    }
  }, [handleNewProject, setChatMode, setFiles]);

  // Wrap handlePrompt to also handle project creation
  const handlePrompt = useCallback(async (prompt: string) => {
    if (generating) return;

    let projectId = activeProjectId;
    if (!projectId) {
      const project = await handleNewProject();
      if (!project) return;
      projectId = project.id;
      setFiles(project.files);
      setChatMode(true);
    }

    if (!projectId) return;
    // Use ref to avoid stale closure on files (which changes on every keystroke)
    generate(prompt, projectId, filesRef.current, setFiles, fetchProjects, setError);
  }, [generating, activeProjectId, handleNewProject, setFiles, setChatMode, fetchProjects, setError, generate]);

  // Back to projects
  const handleBackToProjects = useCallback(() => {
    setActiveProjectId(null);
    setChatMode(false);
  }, [setActiveProjectId, setChatMode]);

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
      />

      {/* File Explorer (only when a project is active) */}
      {activeProject && (
        <FileExplorer
          files={files}
          activeFilePath={activeFilePath}
          onSelectFile={setActiveFilePath}
          onAddFile={handleAddFile}
          onDeleteFile={handleDeleteFile}
          onRenameFile={handleRenameFile}
          collapsed={!showExplorer}
          onToggleCollapse={() => setShowExplorer((prev) => !prev)}
          dirtyFiles={dirtyFiles}
        />
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
        />
      </main>
    </div>
  );
}
