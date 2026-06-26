"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { api } from "../lib/api";
import type { ProjectFile } from "../lib/types";

const SAVE_DEBOUNCE_MS = 800;

export function useFileSave(activeProjectId: string | null) {
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [dirtyFiles, setDirtyFiles] = useState<Set<string>>(new Set());
  const saveTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const projectIdRef = useRef<string | null>(null);
  const filesRef = useRef(files);
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
    } catch (err) {
      console.error("Failed to create file:", err);
    }
  }, [activeProjectId]);

  const handleDeleteFile = useCallback(async (path: string) => {
    if (!activeProjectId) return;
    try {
      await api.deleteFile(activeProjectId, path);
      setFiles((prev) => prev.filter((f) => f.path !== path));
    } catch (err) {
      console.error("Failed to delete file:", err);
    }
  }, [activeProjectId]);

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
    } catch (err) {
      console.error("Failed to rename file:", err);
    }
  }, [activeProjectId, files]);

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
        try {
          await api.upsertFile(activeProjectId!, path, file.content);
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
    handleFilesChange,
    handleAddFile,
    handleDeleteFile,
    handleRenameFile,
  };
}
