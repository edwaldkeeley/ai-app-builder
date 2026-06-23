"use client";

import { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import PromptBar from "./components/PromptBar";
import MainContent from "./components/MainContent";
import { api } from "./lib/api";
import type { ChatMessage, Project, ProjectFile } from "./lib/types";

let chatIdCounter = 0;

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [chatMode, setChatMode] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [files, setFiles] = useState<ProjectFile[]>([]);

  // Fetch projects
  const fetchProjects = useCallback(async () => {
    try {
      setError(null);
      const data = await api.listProjects();
      setProjects(data);
      setActiveProjectId((prev) => {
        if (!prev && data.length > 0) return data[0].id;
        return prev;
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to connect to server";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Fetch project files when active project changes
  useEffect(() => {
    if (!activeProjectId) {
      setFiles([]);
      return;
    }
    api.getProject(activeProjectId).then((detail) => {
      setFiles(detail.files);
    }).catch(() => {
      // Silently fail — the main fetch will surface errors
    });
  }, [activeProjectId]);

  // Create new project
  const handleNewProject = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const project = await api.createProject(`Project ${projects.length + 1}`);
      setProjects((prev) => [project, ...prev]);
      setActiveProjectId(project.id);
      setFiles(project.files);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  };

  // Delete project
  const handleDeleteProject = async (id: string) => {
    if (deleting) return;
    setDeleting(id);
    try {
      await api.deleteProject(id);
      setProjects((prev) => {
        const updated = prev.filter((p) => p.id !== id);
        setActiveProjectId((current) => {
          if (current === id) return updated[0]?.id ?? null;
          return current;
        });
        return updated;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project");
    } finally {
      setDeleting(null);
    }
  };

  // Handle AI prompt
  const handlePrompt = async (prompt: string) => {
    if (generating || !activeProjectId) return;

    // Add user message
    const userMsg: ChatMessage = {
      id: `chat-${++chatIdCounter}`,
      role: "user",
      content: prompt,
      timestamp: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatMode(true);
    setGenerating(true);

    try {
      const result = await api.generate(prompt, activeProjectId);

      // Add AI response
      const aiMsg: ChatMessage = {
        id: `chat-${++chatIdCounter}`,
        role: "assistant",
        content: `Generated ${result.files.length} file${result.files.length !== 1 ? "s" : ""}`,
        files: result.files,
        timestamp: new Date().toISOString(),
      };
      setChatMessages((prev) => [...prev, aiMsg]);

      // Refresh project files
      const detail = await api.getProject(result.project_id);
      setFiles(detail.files);
      setActiveProjectId(result.project_id);

      // Refresh project list
      await fetchProjects();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "AI generation failed";
      setError(msg);
      setChatMessages((prev) => [
        ...prev,
        {
          id: `chat-${++chatIdCounter}`,
          role: "assistant",
          content: `Error: ${msg}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setGenerating(false);
    }
  };

  // Handle file changes from editor
  const handleFilesChange = useCallback((updatedFiles: ProjectFile[]) => {
    setFiles(updatedFiles);
  }, []);

  const activeProject = projects.find((p) => p.id === activeProjectId);

  return (
    <div className="h-dvh flex flex-col">
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          projects={projects}
          activeProjectId={activeProjectId}
          onSelectProject={(id) => {
            setActiveProjectId(id);
            if (chatMode) setChatMode(false);
          }}
          onNewProject={handleNewProject}
          onDeleteProject={handleDeleteProject}
          creating={creating}
          deleting={deleting}
          chatMode={chatMode}
          chatMessages={chatMessages}
          onToggleChat={() => setChatMode(!chatMode)}
        />

        <main className="flex-1 flex flex-col min-w-0">
          <MainContent
            loading={loading}
            error={error}
            activeProject={activeProject}
            files={files}
            onRetry={fetchProjects}
            onCreateProject={handleNewProject}
            creating={creating}
            onFilesChange={handleFilesChange}
          />
        </main>
      </div>

      <PromptBar onSend={handlePrompt} disabled={!activeProject || generating} />
    </div>
  );
}
