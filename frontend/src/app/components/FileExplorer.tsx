"use client";

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import type { ProjectFile } from "../lib/types";
import FileIcon from "../lib/fileIcons";
import { SkeletonExplorer } from "./Skeleton";

interface FileExplorerProps {
  files: ProjectFile[];
  activeFilePath: string | null;
  onSelectFile: (path: string) => void;
  onAddFile: (path: string) => void;
  onDeleteFile: (path: string) => void;
  onRenameFile: (oldPath: string, newPath: string) => void;
  dirtyFiles?: Set<string>;
  loading?: boolean;
}

interface TreeNode {
  name: string;
  path: string;
  type: "file" | "directory";
  children: TreeNode[];
  depth: number;
}

/**
 * Parse a flat list of file paths into a tree structure.
 */
function buildTree(files: ProjectFile[]): TreeNode[] {
  const root: TreeNode[] = [];

  for (const file of files) {
    const parts = file.path.split("/");
    let currentLevel = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;

      if (isLast) {
        // File node
        currentLevel.push({
          name: part,
          path: file.path,
          type: "file",
          children: [],
          depth: i,
        });
      } else {
        // Directory node — find or create
        let dir = currentLevel.find(
          (n) => n.type === "directory" && n.name === part,
        );
        if (!dir) {
          dir = {
            name: part,
            path: parts.slice(0, i + 1).join("/"),
            type: "directory",
            children: [],
            depth: i,
          };
          currentLevel.push(dir);
        }
        currentLevel = dir.children;
      }
    }
  }

  // Sort: directories first, then files, alphabetically within each group
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === "directory" ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const node of nodes) {
      if (node.children.length > 0) sortNodes(node.children);
    }
  };
  sortNodes(root);

  return root;
}

interface FileRowProps {
  node: TreeNode;
  activeFilePath: string | null;
  onSelectFile: (path: string) => void;
  onDeleteFile: (path: string) => void;
  onRenameSubmit: (oldPath: string, newPath: string) => void;
  onAddFile: (path: string) => void;
  dirtyFiles?: Set<string>;
  expandedDirs: Set<string>;
  onToggleDir: (path: string) => void;
}

/** Validate a filename — returns null if valid, or an error message string if invalid. */
function validateFilename(name: string): string | null {
  if (!name || !name.trim()) return "Filename is required";
  if (name.includes("/") || name.includes("\\")) return "Filename cannot contain slashes";
  if (name.includes("..")) return "Filename cannot contain '..'";
  if (/[<>:"|?*]/.test(name)) return "Filename contains invalid characters";
  if (name.length > 255) return "Filename is too long";
  if (name.trim() !== name) return "Filename cannot start or end with spaces";
  return null;
}

function FileRow({
  node,
  activeFilePath,
  onSelectFile,
  onDeleteFile,
  onRenameSubmit,
  onAddFile,
  dirtyFiles,
  expandedDirs,
  onToggleDir,
}: FileRowProps) {
  const expanded = !node.type || node.type !== "directory" || expandedDirs.has(node.path);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(node.name);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showNewFileInput, setShowNewFileInput] = useState(false);
  const [newFileName, setNewFileName] = useState("");
  const [newFileError, setNewFileError] = useState<string | null>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const newFileInputRef = useRef<HTMLInputElement>(null);

  const isActive = node.path === activeFilePath;
  const isDirectory = node.type === "directory";
  const isDirty = !isDirectory && dirtyFiles?.has(node.path);

  // Focus rename input when it appears
  useEffect(() => {
    if (isRenaming) {
      // Select the filename without extension
      const dotIndex = renameValue.lastIndexOf(".");
      const selectionEnd = dotIndex > 0 ? dotIndex : renameValue.length;
      renameInputRef.current?.focus();
      renameInputRef.current?.setSelectionRange(0, selectionEnd);
    }
  }, [isRenaming]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (showNewFileInput) {
      setTimeout(() => newFileInputRef.current?.focus(), 50);
    }
  }, [showNewFileInput]);

  const handleRenameConfirm = () => {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === node.name) {
      setIsRenaming(false);
      setRenameValue(node.name);
      setRenameError(null);
      return;
    }
    const validationError = validateFilename(trimmed);
    if (validationError) {
      setRenameError(validationError);
      return;
    }
    // Compute the new full path
    const parts = node.path.split("/");
    parts[parts.length - 1] = trimmed;
    const newPath = parts.join("/");
    onRenameSubmit(node.path, newPath);
    setIsRenaming(false);
    setRenameError(null);
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleRenameConfirm();
    }
    if (e.key === "Escape") {
      setIsRenaming(false);
      setRenameValue(node.name);
    }
  };

  const handleNewFileSubmit = () => {
    const trimmed = newFileName.trim();
    if (!trimmed) {
      setShowNewFileInput(false);
      return;
    }
    const validationError = validateFilename(trimmed);
    if (validationError) {
      setNewFileError(validationError);
      return;
    }
    const newPath = node.path + "/" + trimmed;
    onAddFile(newPath);
    setShowNewFileInput(false);
    setNewFileName("");
    setNewFileError(null);
    onToggleDir(node.path);
  };

  const handleNewFileKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleNewFileSubmit();
    }
    if (e.key === "Escape") {
      setShowNewFileInput(false);
    }
  };

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (isDirectory) {
        setShowNewFileInput(true);
      }
    },
    [isDirectory],
  );

  const indent = node.depth * 12;

  return (
    <>
      {/* Tree node row */}
      <div
        role="treeitem"
        aria-expanded={isDirectory ? expanded : undefined}
        aria-selected={isActive}
        className={`group flex items-center gap-1 pr-2 py-0.5 text-xs cursor-pointer select-none touch-target-row ${
          isActive
            ? "bg-accent/10 text-accent"
            : "text-text-secondary hover:bg-surface hover:text-foreground"
        }`}
        style={{ paddingLeft: `${12 + indent}px` }}
        onClick={() => {
          if (isDirectory) {
            onToggleDir(node.path);
          } else {
            onSelectFile(node.path);
          }
        }}
        onContextMenu={handleContextMenu}
      >
        {/* Directory chevron or file icon spacer */}
        {isDirectory ? (
          <svg
            className={`w-3 h-3 flex-shrink-0 transition-transform ${
              expanded ? "rotate-90" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        ) : (
          <span className="w-3 h-3 flex-shrink-0 flex items-center justify-center">
            <FileIcon path={node.path} className="w-3.5 h-3.5" />
          </span>
        )}

        {/* Name or rename input */}
        {isRenaming ? (
          <div className="flex-1 flex flex-col gap-0.5">
            <input
              ref={renameInputRef}
              type="text"
              value={renameValue}
              onChange={(e) => { setRenameValue(e.target.value); setRenameError(null); }}
              onKeyDown={handleRenameKeyDown}
              onBlur={handleRenameConfirm}
              className="w-full bg-input border border-accent/50 rounded px-1 py-0 text-xs text-foreground outline-none min-w-0"
              onClick={(e) => e.stopPropagation()}
            />
            {renameError && (
              <span className="text-xs text-danger" role="alert">{renameError}</span>
            )}
          </div>
        ) : (
          <span className="truncate flex-1 flex items-center gap-1">
            {isDirty && <span className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />}
            {node.name}
          </span>
        )}

        {/* Hover actions */}
        {!isRenaming && (
          <span className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity ml-auto">
            {isDirectory ? (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowNewFileInput(true);
                }}
                className="p-0.5 rounded hover:bg-border text-text-secondary hover:text-foreground"
                title="New file"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
              </button>
            ) : null}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsRenaming(true);
                setRenameValue(node.name);
              }}
              className="p-0.5 rounded hover:bg-border text-text-secondary hover:text-foreground"
              title="Rename"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            {!isDirectory && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDeleteConfirm(true);
                }}
                className="p-0.5 rounded hover:bg-danger/20 text-text-secondary hover:text-danger"
                title="Delete"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </span>
        )}
      </div>

      {/* Delete confirmation */}
      {showDeleteConfirm && (
        <div
          className="flex items-center gap-2 px-2 py-1 bg-surface rounded-lg border border-danger/30 animate-fade-in"
          style={{ paddingLeft: `${24 + indent}px` }}
        >
          <span className="text-xs text-danger flex-1">
            Delete <strong>{node.name}</strong>?
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDeleteFile(node.path);
              setShowDeleteConfirm(false);
            }}
            className="px-2 py-0.5 text-xs font-medium rounded bg-danger text-white hover:bg-danger/80 transition-colors"
          >
            Delete
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowDeleteConfirm(false);
            }}
            className="px-2 py-0.5 text-xs font-medium rounded text-text-secondary hover:text-foreground hover:bg-surface transition-colors"
          >
            Cancel
          </button>
        </div>
      )}

      {/* New file input inside directory */}
      {showNewFileInput && (
        <div
          className="flex flex-col px-2 py-0.5 bg-sidebar/50"
          style={{ paddingLeft: `${24 + indent}px` }}
        >
          <div className="flex items-center gap-1">
            <svg className="w-3 h-3 flex-shrink-0 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            <input
              ref={newFileInputRef}
              type="text"
              value={newFileName}
              onChange={(e) => { setNewFileName(e.target.value); setNewFileError(null); }}
              onKeyDown={handleNewFileKeyDown}
              onBlur={() => {
                if (!newFileName.trim()) setShowNewFileInput(false);
              }}
              placeholder="filename.html"
              className="flex-1 bg-input border border-border rounded px-1 py-0 text-xs text-foreground placeholder-text-secondary outline-none focus:border-accent/50 min-w-0"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          {newFileError && (
            <span className="text-xs text-danger mt-0.5" role="alert">{newFileError}</span>
          )}
        </div>
      )}

      {/* Children (directory contents) */}
      {isDirectory && expanded && node.children.length > 0 && (
        <div>
          {node.children.map((child) => (
            <FileRow
              key={child.path}
              node={child}
              activeFilePath={activeFilePath}
              onSelectFile={onSelectFile}
              onDeleteFile={onDeleteFile}
              onRenameSubmit={onRenameSubmit}
              onAddFile={onAddFile}
              dirtyFiles={dirtyFiles}
              expandedDirs={expandedDirs}
              onToggleDir={onToggleDir}
            />
          ))}
        </div>
      )}
    </>
  );
}

export default function FileExplorer({
  files,
  activeFilePath,
  onSelectFile,
  onAddFile,
  onDeleteFile,
  onRenameFile,
  dirtyFiles,
  loading,
}: FileExplorerProps) {
  const [showRootNewFile, setShowRootNewFile] = useState(false);
  const [rootNewFileName, setRootNewFileName] = useState("");
  const [rootNewFileError, setRootNewFileError] = useState<string | null>(null);
  const rootNewFileInputRef = useRef<HTMLInputElement>(null);
  // Persist expanded/collapsed state for directories across re-renders
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());

  const tree = useMemo(() => buildTree(files), [files]);

  const onToggleDir = useCallback((path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (showRootNewFile) {
      setTimeout(() => rootNewFileInputRef.current?.focus(), 50);
    }
  }, [showRootNewFile]);

  const handleRootNewFileSubmit = () => {
    const trimmed = rootNewFileName.trim();
    if (!trimmed) {
      setShowRootNewFile(false);
      return;
    }
    const validationError = validateFilename(trimmed);
    if (validationError) {
      setRootNewFileError(validationError);
      return;
    }
    onAddFile(trimmed);
    setShowRootNewFile(false);
    setRootNewFileName("");
    setRootNewFileError(null);
  };

  const handleRootNewFileKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleRootNewFileSubmit();
    }
    if (e.key === "Escape") {
      setShowRootNewFile(false);
    }
  };

  const explorerPanel = (
    <div
      className="flex flex-col bg-sidebar border-r border-border w-56"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border min-h-[35px]">
        <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Code Files
        </span>
        <button
          onClick={() => setShowRootNewFile(true)}
          className="p-0.5 rounded hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
          title="New file"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* File count */}
      <div className="px-3 py-1 text-xs text-text-secondary border-b border-border">
        {files.length} file{files.length !== 1 ? "s" : ""}
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto py-1 overscroll-contain" role="tree" aria-label="File explorer">
        {loading && tree.length === 0 ? (
          <SkeletonExplorer />
        ) : tree.length === 0 ? (
          <div className="px-3 py-4 text-xs text-text-secondary text-center">
            <p>No files yet.</p>
            <button
              onClick={() => setShowRootNewFile(true)}
              className="mt-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
            >
              + Add File
            </button>
          </div>
        ) : (
          tree.map((node) => (
            <FileRow
              key={node.path}
              node={node}
              activeFilePath={activeFilePath}
              onSelectFile={onSelectFile}
              onDeleteFile={onDeleteFile}
              onRenameSubmit={onRenameFile}
              onAddFile={onAddFile}
              dirtyFiles={dirtyFiles}
              expandedDirs={expandedDirs}
              onToggleDir={onToggleDir}
            />
          ))
        )}

        {/* Root-level new file input */}
        {showRootNewFile && (
          <div className="flex flex-col px-2 py-0.5" style={{ paddingLeft: "12px" }}>
            <div className="flex items-center gap-1">
              <svg className="w-3 h-3 flex-shrink-0 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <input
                ref={rootNewFileInputRef}
                type="text"
                value={rootNewFileName}
                onChange={(e) => { setRootNewFileName(e.target.value); setRootNewFileError(null); }}
                onKeyDown={handleRootNewFileKeyDown}
                onBlur={() => {
                  if (!rootNewFileName.trim()) setShowRootNewFile(false);
                }}
                placeholder="filename.html"
                className="flex-1 bg-input border border-border rounded px-1 py-0 text-xs text-foreground placeholder-text-secondary outline-none focus:border-accent/50 min-w-0"
              />
            </div>
            {rootNewFileError && (
              <span className="text-xs text-danger mt-0.5" role="alert">{rootNewFileError}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );

  return explorerPanel;
}
