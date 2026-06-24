"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "./components/Sidebar";
import MainContent from "./components/MainContent";
import { api } from "./lib/api";
import type { ChatMessage, Project, ProjectFile } from "./lib/types";

let chatIdCounter = 0;

/** Debounce delay for auto-saving file edits (ms). */
const SAVE_DEBOUNCE_MS = 800;

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
  const [savingFiles, setSavingFiles] = useState<Set<string>>(new Set());
  const saveTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Fetch projects
  const fetchProjects = useCallback(async () => {
    try {
      setError(null);
      const data = await api.listProjects();
      setProjects(data);
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

  // Load chat messages when a project is selected
  useEffect(() => {
    if (!activeProjectId) {
      setChatMessages([]);
      return;
    }
    api.getChatMessages(activeProjectId).then((msgs) => {
      const converted: ChatMessage[] = msgs.map((m) => ({
        id: `chat-${m.id}`,
        role: m.role as "user" | "assistant",
        content: m.content,
        files: m.files,
        timestamp: m.created_at,
      }));
      setChatMessages(converted);
      // Set chatIdCounter past the highest ID
      const maxId = msgs.reduce((max, m) => Math.max(max, m.id), 0);
      chatIdCounter = maxId + 1;
    }).catch(() => {});
  }, [activeProjectId]);

  // Fetch project files when active project changes
  useEffect(() => {
    if (!activeProjectId) {
      setFiles([]);
      return;
    }
    api.getProject(activeProjectId).then((detail) => {
      setFiles(detail.files);
    }).catch(() => {});
  }, [activeProjectId]);

  // Create new project
  const handleNewProject = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const project = await api.createProject(`Project ${projects.length + 1}`);
      const projectSummary: Project = {
        id: project.id,
        name: project.name,
        description: project.description,
        status: project.status,
        file_count: project.files.length,
        created_at: project.created_at,
        updated_at: project.updated_at,
      };
      setProjects((prev) => [projectSummary, ...prev]);
      setActiveProjectId(project.id);
      setFiles(project.files);
      setChatMode(true);
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
          if (current === id) {
            const next = updated[0]?.id ?? null;
            if (!next) setChatMode(false);
            return next;
          }
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

  // Select a project — switch to chat mode
  const handleSelectProject = (id: string) => {
    setActiveProjectId(id);
    setChatMode(true);
  };

  // Back to projects — exit chat mode
  const handleBackToProjects = () => {
    setActiveProjectId(null);
    setChatMode(false);
  };

  // Save a chat message to the backend
  const saveMessage = async (projectId: string, role: string, content: string, files?: ProjectFile[]) => {
    try {
      await api.saveChatMessage(projectId, role, content, files);
    } catch (err) {
      console.error("Failed to save chat message:", err);
    }
  };

  // Handle AI prompt — works with or without an active project
  const handlePrompt = async (prompt: string) => {
    if (generating) return;

    // If no active project, create one first
    let projectId = activeProjectId;
    if (!projectId) {
      setCreating(true);
      try {
        const project = await api.createProject(`Project ${projects.length + 1}`);
        const projectSummary: Project = {
          id: project.id,
          name: project.name,
          description: project.description,
          status: project.status,
          file_count: project.files.length,
          created_at: project.created_at,
          updated_at: project.updated_at,
        };
        setProjects((prev) => [projectSummary, ...prev]);
        setActiveProjectId(project.id);
        setFiles(project.files);
        setChatMode(true);
        projectId = project.id;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create project");
        setCreating(false);
        return;
      } finally {
        setCreating(false);
      }
    }

    if (!projectId) return;

    // Add user message
    const userMsg: ChatMessage = {
      id: `chat-${++chatIdCounter}`,
      role: "user",
      content: prompt,
      timestamp: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setGenerating(true);

    // Save user message to backend
    saveMessage(projectId, "user", prompt);

    try {
      const result = await api.generate(prompt, projectId);

      // Add AI response with the message from the AI
      const aiMsg: ChatMessage = {
        id: `chat-${++chatIdCounter}`,
        role: "assistant",
        content: result.message || `Generated ${result.files.length} file${result.files.length !== 1 ? "s" : ""}`,
        files: result.files,
        timestamp: new Date().toISOString(),
      };
      setChatMessages((prev) => [...prev, aiMsg]);

      // Save AI response to backend
      saveMessage(projectId, "assistant", aiMsg.content, result.files);

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

  // Handle file changes from editor — detect which file changed and set a save timer
  const handleFilesChange = useCallback((updatedFiles: ProjectFile[]) => {
    setFiles((prev) => {
      // Find which file(s) actually changed content
      for (const updated of updatedFiles) {
        const prevFile = prev.find((f) => f.path === updated.path);
        if (!prevFile || prevFile.content !== updated.content) {
          // Cancel any existing timer for this path
          const existing = saveTimersRef.current.get(updated.path);
          if (existing) clearTimeout(existing);

          // Set a new debounced save timer
          const timer = setTimeout(async () => {
            saveTimersRef.current.delete(updated.path);
            setSavingFiles((s) => new Set(s).add(updated.path));
            try {
              await api.upsertFile(activeProjectId!, updated.path, updated.content);
            } catch (err) {
              console.error(`Failed to save ${updated.path}:`, err);
            } finally {
              setSavingFiles((s) => {
                const next = new Set(s);
                next.delete(updated.path);
                return next;
              });
            }
          }, SAVE_DEBOUNCE_MS);

          saveTimersRef.current.set(updated.path, timer);
        }
      }
      return updatedFiles;
    });
  }, [activeProjectId]);

  const activeProject: Project | null = projects.find((p) => p.id === activeProjectId) ?? null;

  return (
    <div className="h-dvh flex">
      <Sidebar
        projects={projects}
        activeProjectId={activeProjectId}
        onSelectProject={handleSelectProject}
        onNewProject={handleNewProject}
        onDeleteProject={handleDeleteProject}
        creating={creating}
        deleting={deleting}
        chatMode={chatMode}
        chatMessages={chatMessages}
        generating={generating}
        onSendPrompt={handlePrompt}
        onBackToProjects={handleBackToProjects}
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
          onSendPrompt={handlePrompt}
          generating={generating}
        />
      </main>
    </div>
  );
}
