"use client";

import { useState, useCallback, useEffect } from "react";
import { api } from "../lib/api";
import type { Project } from "../lib/types";

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

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
    const timer = setTimeout(() => fetchProjects(), 0);
    return () => clearTimeout(timer);
  }, [fetchProjects]);

  const handleNewProject = useCallback(async () => {
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
      return project;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
      return null;
    } finally {
      setCreating(false);
    }
  }, [creating, projects.length]);

  const handleDeleteProject = useCallback(async (id: string) => {
    if (deleting) return;
    setDeleting(id);
    try {
      await api.deleteProject(id);
      setProjects((prev) => {
        const updated = prev.filter((p) => p.id !== id);
        setActiveProjectId((current) => {
          if (current === id) {
            return updated[0]?.id ?? null;
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
  }, [deleting]);

  const handleSelectProject = useCallback((id: string) => {
    setActiveProjectId(id);
  }, []);

  const activeProject: Project | null = projects.find((p) => p.id === activeProjectId) ?? null;

  return {
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
    handleSelectProject,
  };
}
