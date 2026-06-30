"use client";

import { useState } from "react";
import type { ChatMessage, Project } from "../lib/types";
import type { WritingStatus } from "../hooks/useChat";
import ChatPanel from "./ChatPanel";
import { SkeletonSidebar } from "./Skeleton";

interface SidebarProps {
  projects: Project[];
  activeProjectId: string | null;
  onSelectProject: (id: string) => void;
  onNewProject: () => void;
  onDeleteProject: (id: string) => void;
  creating: boolean;
  deleting: string | null;
  chatMode: boolean;
  chatMessages: ChatMessage[];
  generating: boolean;
  writingStatus?: WritingStatus | null;
  onSendPrompt: (prompt: string) => void;
  onBackToProjects: () => void;
  loading?: boolean;
  isMobile?: boolean;
  showMobileSidebar?: boolean;
  onCloseMobileSidebar?: () => void;
}

export default function Sidebar({
  projects,
  activeProjectId,
  onSelectProject,
  onNewProject,
  onDeleteProject,
  creating,
  deleting,
  chatMode,
  chatMessages,
  generating,
  writingStatus,
  onSendPrompt,
  onBackToProjects,
  loading,
  isMobile,
  onCloseMobileSidebar,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const handleDelete = (id: string) => {
    if (confirmDelete === id) {
      setConfirmDelete(null);
      onDeleteProject(id);
    } else {
      setConfirmDelete(id);
    }
  };

  // On mobile, render as overlay panel
  const sidebarPanel = (content: React.ReactNode) => {
    if (!isMobile) return content;
    return (
      <>
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={onCloseMobileSidebar}
        />
        {/* Overlay panel */}
        <div className="fixed inset-y-0 left-0 z-50 shadow-xl">
          {content}
        </div>
      </>
    );
  };

  // Collapsed state — icon button
  if (collapsed) {
    return sidebarPanel(
      <aside id="sidebar-panel" className="flex flex-col items-center py-3 px-1 bg-sidebar border-r border-border">
        <button
          onClick={() => setCollapsed(false)}
          className="p-2 rounded-lg hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
          title={chatMode ? "Show chat" : "Show projects"}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
        <div className="flex-1" />
        {!chatMode && (
          <button
            onClick={onNewProject}
            disabled={creating}
            className="p-2 rounded-lg hover:bg-surface text-text-secondary hover:text-foreground disabled:opacity-40 transition-colors"
            title="New project"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
          </button>
        )}
      </aside>
    );
  }

  // Chat mode — show chat panel in sidebar
  if (chatMode) {
    return sidebarPanel(
      <aside id="sidebar-panel" className="flex flex-col w-80 bg-sidebar border-r border-border">
        {/* Header with back button */}
        <div className="flex items-center gap-2 px-3 py-3 border-b border-border">
          <button
            onClick={onBackToProjects}
            className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
            title="Back to projects"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm font-semibold truncate">
            {projects.find((p) => p.id === activeProjectId)?.name ?? "Chat"}
          </span>
          <button
            onClick={() => setCollapsed(true)}
            className="ml-auto p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
            title="Collapse sidebar"
            aria-expanded={!collapsed}
            aria-controls="sidebar-panel"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        </div>
        {/* Chat panel fills the rest */}
        <div className="flex-1 flex flex-col min-h-0">
          <ChatPanel
            messages={chatMessages}
            onSend={onSendPrompt}
            disabled={false}
            generating={generating}
            writingStatus={writingStatus}
          />
        </div>
      </aside>
    );
  }

  // Project list mode
  return sidebarPanel(
    <aside id="sidebar-panel" className="flex flex-col w-72 bg-sidebar border-r border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md bg-accent flex items-center justify-center flex-shrink-0">
            <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <span className="text-sm font-semibold truncate">Projects</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onNewProject}
            disabled={creating}
            className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground disabled:opacity-40 transition-colors"
            title="New project"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
          </button>
          <button
            onClick={() => setCollapsed(true)}
            className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
            title="Collapse sidebar"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Project list */}
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {loading && projects.length === 0 ? (
          <SkeletonSidebar />
        ) : projects.length === 0 ? (
          <div className="text-xs text-text-secondary text-center py-8 px-4">
            <p>No projects yet.</p>
            <p className="mt-1">Click + to create one.</p>
          </div>
        ) : (
          projects.map((project) => {
            const isDeleting = deleting === project.id;
            const isConfirming = confirmDelete === project.id;

            return (
              <div key={project.id} className="relative">
                {isConfirming && (
                  <div className="absolute inset-0 z-10 flex items-center gap-1 px-2 bg-surface rounded-lg border border-danger/30">
                    <span className="text-xs text-text-secondary flex-1">Delete?</span>
                    <button
                      onClick={() => handleDelete(project.id)}
                      disabled={isDeleting}
                      className="px-2 py-0.5 text-xs rounded bg-danger text-white hover:bg-danger/80 disabled:opacity-50 transition-colors"
                    >
                      {isDeleting ? "..." : "Yes"}
                    </button>
                    <button
                      onClick={() => setConfirmDelete(null)}
                      className="px-2 py-0.5 text-xs rounded hover:bg-border text-text-secondary transition-colors"
                    >
                      No
                    </button>
                  </div>
                )}
                <div
                  onClick={() => {
                    setConfirmDelete(null);
                    onSelectProject(project.id);
                  }}
                  role="button"
                  tabIndex={isConfirming ? -1 : 0}
                  aria-hidden={isConfirming}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setConfirmDelete(null);
                      onSelectProject(project.id);
                    }
                  }}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors group cursor-pointer ${
                    activeProjectId === project.id
                      ? "bg-surface text-foreground"
                      : "text-text-secondary hover:bg-surface hover:text-foreground"
                  } ${isConfirming ? "opacity-40 pointer-events-none" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="truncate font-medium">{project.name}</span>
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(project.id);
                      }}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          handleDelete(project.id);
                        }
                      }}
                      className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-border text-text-secondary hover:text-danger transition-all cursor-pointer"
                      title="Delete project"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </span>
                  </div>
                  <div className="text-xs text-text-secondary mt-0.5">
                    {project.file_count} file{project.file_count !== 1 ? "s" : ""}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Bottom section */}
      <div className="border-t border-border p-2">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-text-secondary">
          <div className="w-2 h-2 rounded-full bg-accent" />
          <span>Connected</span>
        </div>
      </div>
    </aside>
  );
}
