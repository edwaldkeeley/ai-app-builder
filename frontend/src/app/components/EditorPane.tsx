"use client";

import { useRef, useCallback } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { ProjectFile } from "../lib/types";

interface EditorPaneProps {
  files: ProjectFile[];
  activeFilePath: string | null;
  onSelectFile: (path: string) => void;
  onFileContentChange: (path: string, content: string) => void;
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
}: EditorPaneProps) {
  const editorRef = useRef<any>(null);

  const activeFile = files.find((f) => f.path === activeFilePath) ?? files[0];
  const language = activeFile ? LANGUAGE_MAP[activeFile.file_type] || "plaintext" : "plaintext";

  const handleEditorDidMount: OnMount = useCallback((editor) => {
    editorRef.current = editor;
  }, []);

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (activeFile && value !== undefined) {
        onFileContentChange(activeFile.path, value);
      }
    },
    [activeFile, onFileContentChange],
  );

  if (files.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-text-secondary">
        No files to display.
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* File tabs */}
      <div className="flex items-center gap-0.5 px-2 pt-2 bg-sidebar border-b border-border overflow-x-auto">
        {files.map((file) => (
          <button
            key={file.path}
            onClick={() => onSelectFile(file.path)}
            className={`px-3 py-1.5 text-xs font-medium rounded-t-md border border-border border-b-0 transition-colors whitespace-nowrap ${
              (activeFile?.path === file.path)
                ? "bg-background text-foreground border-b-background"
                : "bg-sidebar text-text-secondary hover:text-foreground"
            }`}
          >
            {file.path.split("/").pop()}
          </button>
        ))}
      </div>

      {/* Monaco editor */}
      <div className="flex-1 min-h-0">
        <Editor
          key={activeFile?.path}
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
  );
}
