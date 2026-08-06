"use client";

import { memo, useRef, useCallback, useState, useEffect, useMemo } from "react";
import Editor, { type OnMount, type BeforeMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import type { ProjectFile } from "@/app/lib/types";
import FileExplorer from "@/features/editor/components/FileExplorer";
import { SkeletonEditor } from "@/components/ui/Skeleton";
import { useTheme } from "@/features/layout/contexts/ThemeContext";

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
  typescript: "typescript",
  tsx: "typescript",
  jsx: "javascript",
  json: "json",
  python: "python",
  markdown: "markdown",
  svg: "xml",
};

const EDITOR_OPTIONS: editor.IStandaloneEditorConstructionOptions = {
  fontSize: 13,
  fontFamily: "var(--font-geist-mono), monospace",
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  lineNumbers: "on",
  tabSize: 2,
  automaticLayout: false,
  padding: { top: 8 },
  suggest: { showKeywords: false, showSnippets: false },
  hover: { enabled: true, delay: 500 },
  folding: true,
  foldingHighlight: false,
  renderLineHighlight: "line" as const,
  renderWhitespace: "selection" as const,
  selectionHighlight: true,
  codeLens: false,
  colorDecorators: false,
  maxTokenizationLineLength: 2000,
};

const EditorPane = memo(function EditorPane({
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
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    filesRef.current = files;
  }, [files]);
  useEffect(() => {
    activeFilePathRef.current = activeFilePath;
  }, [activeFilePath]);

  const activeFile = useMemo(
    () => files.find((f) => f.path === activeFilePath) ?? files[0],
    [files, activeFilePath],
  );
  const language = useMemo(
    () => (activeFile ? LANGUAGE_MAP[activeFile.file_type] || "plaintext" : "plaintext"),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeFile?.file_type],
  );
  const activeFileKey = activeFile?.path ?? null;

  useEffect(() => {
    const editor = editorRef.current;
    const container = containerRef.current;
    if (!editor || !container) return;
    const observer = new ResizeObserver(() => {
      editor.layout();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [editorReady]);

  const prevPathSetRef = useRef<string[] | null>(null);

  useEffect(() => {
    const monaco = monacoRef.current;
    if (!monaco) return;
    const paths = files.map((f) => f.path);
    const prev = prevPathSetRef.current;
    // Only dispose models when the SET of paths actually changes (skip on content-only updates)
    if (prev && prev.length === paths.length && prev.every((p, i) => p === paths[i])) {
      return;
    }
    prevPathSetRef.current = paths;
    const activePaths = new Set(paths);
    for (const model of monaco.editor.getModels()) {
      const modelPath = (model.uri as { path?: string }).path?.replace(/^\//, "") || "";
      if (modelPath && !activePaths.has(modelPath)) {
        model.dispose();
      }
    }
  }, [files]);

  const handleBeforeMount: BeforeMount = useCallback((monaco) => {
    if (typeof monaco.editor.setColorDecorationsEnabled === "function") {
      monaco.editor.setColorDecorationsEnabled(false);
    }
  }, []);

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
  }, [activeFileKey, language]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco || !activeFile) return;
    const uri = monaco.Uri.parse(`file:///${activeFile.path}`);
    const model = monaco.editor.getModel(uri);
    if (model && model.getValue() !== activeFile.content) {
      model.pushEditOperations(
        [],
        [
          {
            range: model.getFullModelRange(),
            text: activeFile.content,
          },
        ],
        () => null,
      );
      model.pushStackElement();
    }
  }, [activeFileKey, activeFile?.content]); // eslint-disable-line react-hooks/exhaustive-deps

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
      <div className="flex-1 flex min-h-0">
        <FileExplorer
          files={files}
          activeFilePath={activeFilePath}
          onSelectFile={onSelectFile}
          onAddFile={onAddFile}
          onDeleteFile={onDeleteFile}
          onRenameFile={onRenameFile}
          dirtyFiles={dirtyFiles}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-sidebar border-b border-border text-xs text-text-secondary animate-slide-down">
            <span className="font-medium text-foreground truncate">
              {activeFile?.path || "No file selected"}
            </span>
            {activeFile && dirtyFiles?.has(activeFile.path) && (
              <span className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" title="Unsaved changes" />
            )}
          </div>
          <div ref={containerRef} className="flex-1 min-h-0 relative">
            {!editorReady && <SkeletonEditor />}
            <div className={editorReady ? "absolute inset-0" : "invisible h-0"}>
              <Editor
                beforeMount={handleBeforeMount}
                defaultLanguage={language}
                language={language}
                onChange={handleChange}
                onMount={handleEditorDidMount}
                theme={theme === "dark" ? "vs-dark" : "vs"}
                options={EDITOR_OPTIONS}
                loading={null}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

export default EditorPane;
