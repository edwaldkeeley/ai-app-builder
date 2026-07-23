"use client";

import { useRef, useCallback, useState, useEffect } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import type { ProjectFile } from "../lib/types";
import FileExplorer from "./FileExplorer";
import { SkeletonEditor } from "./Skeleton";
import { useTheme } from "../contexts/ThemeContext";

interface EditorPaneProps {
  files: ProjectFile[];
  activeFilePath: string | null;
  onSelectFile: (path: string) => void;
  onFileContentChange: (path: string, content: string) => void;
  onAddFile: (path: string) => void;
  onDeleteFile: (path: string) => void;
  onRenameFile: (oldPath: string, newPath: string) => void;
  dirtyFiles?: Set<string>;
}

const LANGUAGE_MAP: Record<string, string> = {
  html: "html",
  css: "css",
  javascript: "javascript",
  json: "json",
  python: "python",
};

export default function EditorPane({
  files,
  activeFilePath,
  onSelectFile,
  onFileContentChange,
  onAddFile,
  onDeleteFile,
  onRenameFile,
  dirtyFiles,
}: EditorPaneProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const monacoRef = useRef<any>(null);
  const filesRef = useRef(files);
  const activeFilePathRef = useRef(activeFilePath);
  const [editorReady, setEditorReady] = useState(false);
  const { theme } = useTheme();

  // Keep refs in sync with props
  useEffect(() => {
    filesRef.current = files;
  }, [files]);
  useEffect(() => {
    activeFilePathRef.current = activeFilePath;
  }, [activeFilePath]);

  const activeFile = files.find((f) => f.path === activeFilePath) ?? files[0];
  const language = activeFile ? LANGUAGE_MAP[activeFile.file_type] || "plaintext" : "plaintext";

  // ── Monaco model management ──

  const handleEditorDidMount: OnMount = useCallback((editorInstance, monaco) => {
    editorRef.current = editorInstance;
    monacoRef.current = monaco;
    setEditorReady(true);

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
      const path = activeFilePathRef.current;
      if (!path) return;
      onFileContentChange(path, value);
    },
    [onFileContentChange],
  );

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* File explorer + editor side by side */}
      <div className="flex-1 flex min-h-0">
        {/* Code Files panel (embedded FileExplorer) */}
        <FileExplorer
          files={files}
          activeFilePath={activeFilePath}
          onSelectFile={onSelectFile}
          onAddFile={onAddFile}
          onDeleteFile={onDeleteFile}
          onRenameFile={onRenameFile}
          dirtyFiles={dirtyFiles}
        />

        {/* Editor column: filename bar on top, editor below */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Filename bar — shows the active file name */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-sidebar border-b border-border text-xs text-text-secondary animate-slide-down">
            <span className="font-medium text-foreground truncate">
              {activeFile?.path || "No file selected"}
            </span>
            {activeFile && dirtyFiles?.has(activeFile.path) && (
              <span className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" title="Unsaved changes" />
            )}
          </div>

          {/* Monaco editor */}
          <div className="flex-1 min-h-0 relative">
            {!editorReady && <SkeletonEditor />}
            <div className={editorReady ? "absolute inset-0" : "invisible h-0"}>
              <Editor
                defaultLanguage={language}
                language={language}
                value={activeFile?.content ?? ""}
                onChange={handleChange}
                onMount={handleEditorDidMount}
                theme={theme === "dark" ? "vs-dark" : "vs"}
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
      </div>
    </div>
  );
}
