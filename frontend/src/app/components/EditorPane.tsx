"use client";

import { useRef, useCallback, useState, useEffect } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import type { ProjectFile } from "../lib/types";
import { SkeletonEditor } from "./Skeleton";
import { useToast } from "./Toast";

interface EditorPaneProps {
  files: ProjectFile[];
  activeFilePath: string | null;
  onSelectFile: (path: string) => void;
  onFileContentChange: (path: string, content: string) => void;
  onAddFile: (path: string) => void;
}

const LANGUAGE_MAP: Record<string, string> = {
  html: "html",
  css: "css",
  javascript: "javascript",
  json: "json",
  python: "python",
};

const FILE_EXTENSIONS = [".html", ".css", ".js", ".json", ".py"];

export default function EditorPane({
  files,
  activeFilePath,
  onSelectFile,
  onFileContentChange,
  onAddFile,
}: EditorPaneProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const monacoRef = useRef<any>(null);
  const filesRef = useRef(files);
  const activeFilePathRef = useRef(activeFilePath);
  const [showNewFileInput, setShowNewFileInput] = useState(false);
  const [newFileName, setNewFileName] = useState("");
  const [editorReady, setEditorReady] = useState(false);
  const newFileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  // Keep refs in sync with props
  useEffect(() => {
    filesRef.current = files;
  }, [files]);
  useEffect(() => {
    activeFilePathRef.current = activeFilePath;
  }, [activeFilePath]);

  const activeFile = files.find((f) => f.path === activeFilePath) ?? files[0];
  const language = activeFile ? LANGUAGE_MAP[activeFile.file_type] || "plaintext" : "plaintext";

  // ── Monaco model management: preserve editor state across tab switches ──

  const handleEditorDidMount: OnMount = useCallback((editorInstance, monaco) => {
    editorRef.current = editorInstance;
    monacoRef.current = monaco;
    setEditorReady(true);

    // Use refs to access latest props (avoids stale closure from [] deps)
    const currentFiles = filesRef.current;
    const currentActivePath = activeFilePathRef.current;
    const file = currentFiles.find((f) => f.path === currentActivePath) ?? currentFiles[0];
    if (file) {
      const uri = monaco.Uri.parse(`file:///${file.path}`);
      let model = monaco.editor.getModel(uri);
      if (!model) {
        model = monaco.editor.createModel(file.content, LANGUAGE_MAP[file.file_type] || "plaintext", uri);
      }
      editorInstance.setModel(model);
    }
  }, []);

  // Switch models when active file changes
  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco || !activeFile) return;

    const uri = monaco.Uri.parse(`file:///${activeFile.path}`);
    let model = monaco.editor.getModel(uri);
    if (!model) {
      model = monaco.editor.createModel(activeFile.content, language, uri);
    }
    if (editor.getModel() !== model) {
      editor.setModel(model);
    }
  }, [activeFile?.path]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync model content when files change externally (e.g., AI streaming)
  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco || !activeFile) return;

    const uri = monaco.Uri.parse(`file:///${activeFile.path}`);
    const model = monaco.editor.getModel(uri);
    if (model && model.getValue() !== activeFile.content) {
      model.setValue(activeFile.content);
    }
  }, [activeFile?.content]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (value === undefined) return;
      // Use ref to always read the latest active file path (avoids stale closure)
      const path = activeFilePathRef.current;
      if (!path) return;
      onFileContentChange(path, value);
    },
    [onFileContentChange],
  );

  const handleAddFileClick = () => {
    setNewFileName("");
    setShowNewFileInput(true);
    setTimeout(() => newFileInputRef.current?.focus(), 50);
  };

  const handleNewFileSubmit = () => {
    const trimmed = newFileName.trim();
    if (!trimmed) {
      setShowNewFileInput(false);
      return;
    }

    // Auto-append extension if none provided
    let finalPath = trimmed;
    const hasExtension = FILE_EXTENSIONS.some((ext) => trimmed.endsWith(ext));
    if (!hasExtension) {
      finalPath = `${trimmed}.html`;
    }

    // Check for duplicate
    if (files.some((f) => f.path === finalPath)) {
      showToast("error", `File "${finalPath}" already exists`);
      return;
    }

    onAddFile(finalPath);
    setNewFileName("");
    setShowNewFileInput(false);
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

  if (files.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-sm text-text-secondary">
        <p>No files yet.</p>
        <button
          onClick={handleAddFileClick}
          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
        >
          + Add File
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* File tabs — click to switch files, no delete here (use file explorer) */}
      <div className="flex items-center gap-0.5 px-2 pt-2 bg-sidebar border-b border-border overflow-x-auto">
        {files.map((file) => (
          <div
            key={file.path}
            className={`flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-t-md border border-border border-b-0 transition-colors whitespace-nowrap cursor-pointer ${
              (activeFile?.path === file.path)
                ? "bg-background text-foreground border-b-background"
                : "bg-sidebar text-text-secondary hover:text-foreground"
            }`}
            onClick={() => onSelectFile(file.path)}
          >
            <span>{file.path.split("/").pop()}</span>
          </div>
        ))}

        {/* Add file button */}
        <button
          onClick={handleAddFileClick}
          className="flex-shrink-0 px-2 py-1.5 text-xs text-text-secondary hover:text-foreground transition-colors rounded-t-md hover:bg-sidebar/80"
          title="Add new file"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* New file inline input */}
      {showNewFileInput && (
        <div className="flex items-center gap-2 px-3 py-2 bg-sidebar border-b border-border">
          <input
            ref={newFileInputRef}
            type="text"
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            onKeyDown={handleNewFileKeyDown}
            placeholder="filename.html"
            className="flex-1 bg-input border border-border rounded-md px-2 py-1 text-xs text-foreground placeholder-text-secondary outline-none focus:border-accent/50"
          />
          <button
            onClick={handleNewFileSubmit}
            disabled={!newFileName.trim()}
            className="px-2 py-1 text-xs font-medium rounded-md bg-accent text-white hover:bg-accent-hover disabled:opacity-40 transition-colors"
          >
            Add
          </button>
          <button
            onClick={() => setShowNewFileInput(false)}
            className="px-2 py-1 text-xs font-medium rounded-md text-text-secondary hover:text-foreground hover:bg-surface transition-colors"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Monaco editor with skeleton while loading */}
      <div className="flex-1 min-h-0 relative">
        {!editorReady && <SkeletonEditor />}
        <div className={editorReady ? "absolute inset-0" : "invisible h-0"}>
          <Editor
            defaultLanguage={language}
            language={language}
            value={activeFile?.content ?? ""}
            onChange={handleChange}
            onMount={handleEditorDidMount}
            theme="vs-dark"
            options={{
              fontSize: 13,
              fontFamily: "var(--font-geist-mono), monospace",
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              lineNumbers: "on",
              tabSize: 2,
              automaticLayout: true,
              padding: { top: 8 },
            }}
          />
        </div>
      </div>
    </div>
  );
}
