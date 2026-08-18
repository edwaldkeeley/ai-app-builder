"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { api } from "@/app/lib/api";
import type { Project } from "@/app/lib/types";
import { useToast } from "@/components/ui/Toast";

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const { showToast } = useToast();
  const projectCounterRef = useRef(0);

  const fetchProjects = useCallback(async () => {
    try {
      setError(null);
      const data = await api.listProjects();
      setProjects(data);
      projectCounterRef.current = data.length;
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

  const handleNewProject = useCallback(async (name?: string) => {
    if (creating) return;
    setCreating(true);
    try {
      const projectName = name?.trim() ? name.trim().slice(0, 128) : `Project ${++projectCounterRef.current}`;
      const project = await api.createProject(projectName);
      const projectSummary: Project = {
        id: project.id,
        name: project.name,
        description: project.description,
        status: project.status,
        framework: project.framework,
        file_count: project.files.length,
        created_at: project.created_at,
        updated_at: project.updated_at,
      };
      setProjects((prev) => [projectSummary, ...prev]);
      setActiveProjectId(project.id);
      showToast("success", `Created "${project.name}"`);
      return project;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create project";
      setError(msg);
      showToast("error", msg);
      return null;
    } finally {
      setCreating(false);
    }
  }, [creating, showToast]);

  const projectsRef = useRef(projects);
  useEffect(() => { projectsRef.current = projects; }, [projects]);

  const handleDeleteProject = useCallback(async (id: string) => {
    if (deleting) return;
    setDeleting(id);
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
      // Update active project if the deleted one was active
      setActiveProjectId((current) => {
        if (current === id) {
          // Read from ref to avoid stale closure
          const remaining = projectsRef.current.filter((p) => p.id !== id);
          return remaining[0]?.id ?? null;
        }
        return current;
      });
      const deletedName = projectsRef.current.find((p) => p.id === id)?.name || "Project";
      showToast("success", `Deleted "${deletedName}"`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete project";
      setError(msg);
      showToast("error", msg);
    } finally {
      setDeleting(null);
    }
  }, [deleting, showToast]);

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
