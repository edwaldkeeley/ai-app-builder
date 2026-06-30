"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { api } from "../lib/api";
import type { ProjectFile } from "../lib/types";
import { useToast } from "../components/Toast";

const SAVE_DEBOUNCE_MS = 800;

export type SaveStatus = "idle" | "saving" | "saved" | "error";

export function useFileSave(activeProjectId: string | null) {
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [dirtyFiles, setDirtyFiles] = useState<Set<string>>(new Set());
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const saveTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const projectIdRef = useRef<string | null>(null);
  const filesRef = useRef(files);
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { showToast } = useToast();
  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  // Track current project ID and clear pending saves when switching projects
  useEffect(() => {
    projectIdRef.current = activeProjectId;
    saveTimersRef.current.forEach((timer) => clearTimeout(timer));
    saveTimersRef.current.clear();
    const timer = setTimeout(() => setDirtyFiles(new Set()), 0);
    return () => clearTimeout(timer);
  }, [activeProjectId]);

  const handleAddFile = useCallback(async (path: string) => {
    if (!activeProjectId) return;
    try {
      const newFile = await api.upsertFile(activeProjectId, path, "");
      setFiles((prev) => [...prev, newFile]);
      showToast("success", `Created ${path}`);
    } catch (err) {
      console.error("Failed to create file:", err);
      showToast("error", `Failed to create ${path}`);
    }
  }, [activeProjectId, showToast]);

  const handleDeleteFile = useCallback(async (path: string) => {
    if (!activeProjectId) return;
    try {
      await api.deleteFile(activeProjectId, path);
      setFiles((prev) => prev.filter((f) => f.path !== path));
      showToast("success", `Deleted ${path}`);
    } catch (err) {
      console.error("Failed to delete file:", err);
      showToast("error", `Failed to delete ${path}`);
    }
  }, [activeProjectId, showToast]);

  const handleRenameFile = useCallback(async (oldPath: string, newPath: string) => {
    if (!activeProjectId) return;
    try {
      const oldFile = files.find((f) => f.path === oldPath);
      if (!oldFile) return;
      await api.upsertFile(activeProjectId, newPath, oldFile.content);
      await api.deleteFile(activeProjectId, oldPath);
      setFiles((prev) =>
        prev.map((f) =>
          f.path === oldPath ? { ...f, path: newPath } : f,
        ),
      );
      showToast("success", `Renamed to ${newPath}`);
    } catch (err) {
      console.error("Failed to rename file:", err);
      showToast("error", `Failed to rename file`);
    }
  }, [activeProjectId, files, showToast]);

  const handleFilesChange = useCallback((updatedFiles: ProjectFile[]) => {
    const pathsToMarkDirty: string[] = [];
    setFiles((prev) => {
      // Merge: update existing files by path, add new ones, keep unchanged ones
      const merged = new Map(prev.map((f) => [f.path, f]));
      for (const updated of updatedFiles) {
        const prevFile = merged.get(updated.path);
        if (!prevFile || prevFile.content !== updated.content) {
          pathsToMarkDirty.push(updated.path);
        }
        merged.set(updated.path, updated);
      }
      return Array.from(merged.values());
    });

    // Schedule saves for dirty files (outside updater to avoid side effects)
    for (const path of pathsToMarkDirty) {
      const existing = saveTimersRef.current.get(path);
      if (existing) clearTimeout(existing);

      setDirtyFiles((prev) => new Set(prev).add(path));

      const timer = setTimeout(async () => {
        saveTimersRef.current.delete(path);
        if (projectIdRef.current !== activeProjectId) return;
        const currentFiles = filesRef.current; // We need the latest file content
        const file = currentFiles.find((f) => f.path === path);
        if (!file) return;
        setSaveStatus("saving");
        try {
          await api.upsertFile(activeProjectId!, path, file.content);
          setSaveStatus("saved");
          // Clear "saved" status after 2 seconds
          if (savedTimerRef.current) clearTimeout(savedTimerRef.current);
          savedTimerRef.current = setTimeout(() => {
            setSaveStatus((prev) => (prev === "saved" ? "idle" : prev));
          }, 2000);
        } catch {
          setSaveStatus("error");
        } finally {
          setDirtyFiles((prev) => {
            const next = new Set(prev);
            next.delete(path);
            return next;
          });
        }
      }, SAVE_DEBOUNCE_MS);

      saveTimersRef.current.set(path, timer);
    }
  }, [activeProjectId]);

  return {
    files,
    setFiles,
    dirtyFiles,
    saveStatus,
    handleFilesChange,
    handleAddFile,
    handleDeleteFile,
    handleRenameFile,
  };
}
