"use client";

import { useState } from "react";
import type { ChatMessage, Project } from "../lib/types";

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
  onToggleChat: () => void;
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
  onToggleChat,
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

  // Collapsed state — icon button
  if (collapsed) {
    return (
      <aside className="flex flex-col items-center py-3 px-1 bg-sidebar border-r border-border">
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
      </aside>
    );
  }

  return (
    <aside className="flex flex-col w-72 bg-sidebar border-r border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md bg-accent flex items-center justify-center flex-shrink-0">
            <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <span className="text-sm font-semibold truncate">
            {chatMode ? "Chat" : "Projects"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {chatMode ? (
            <button
              onClick={onToggleChat}
              className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
              title="Show projects"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          ) : (
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
          )}
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {chatMode ? (
          /* Chat messages */
          chatMessages.length === 0 ? (
            <div className="text-xs text-text-secondary text-center py-8 px-4">
              <p>No messages yet.</p>
              <p className="mt-1">Ask the AI to build something.</p>
            </div>
          ) : (
            chatMessages.map((msg) => (
              <div
                key={msg.id}
                className={`px-3 py-2 rounded-lg text-sm ${
                  msg.role === "user"
                    ? "bg-accent/10 text-foreground"
                    : "text-text-secondary"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium uppercase tracking-wider text-text-secondary">
                    {msg.role === "user" ? "You" : "AI"}
                  </span>
                  <span className="text-[10px] text-text-secondary">
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-xs line-clamp-3">{msg.content}</p>
                {msg.files && msg.files.length > 0 && (
                  <p className="text-xs text-accent mt-1">
                    {msg.files.length} file{msg.files.length !== 1 ? "s" : ""} generated
                  </p>
                )}
              </div>
            ))
          )
        ) : (
          /* Project list */
          projects.length === 0 ? (
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
                  <button
                    key={project.id}
                    onClick={() => {
                      setConfirmDelete(null);
                      onSelectProject(project.id);
                    }}
                    disabled={isDeleting}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors group disabled:opacity-50 ${
                      activeProjectId === project.id
                        ? "bg-surface text-foreground"
                        : "text-text-secondary hover:bg-surface hover:text-foreground"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="truncate font-medium">{project.name}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(project.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-border text-text-secondary hover:text-danger transition-all"
                        title="Delete project"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                    <div className="text-xs text-text-secondary mt-0.5">
                      {project.file_count} file{project.file_count !== 1 ? "s" : ""}
                    </div>
                  </button>
                </div>
              );
            })
          )
        )}
      </div>

      {/* Bottom section */}
      <div className="border-t border-border p-2">
        {chatMode && chatMessages.length > 0 && (
          <button
            onClick={onToggleChat}
            className="w-full text-left px-3 py-2 rounded-lg text-xs text-text-secondary hover:bg-surface hover:text-foreground transition-colors mb-1"
          >
            ← Back to projects
          </button>
        )}
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-text-secondary">
          <div className="w-2 h-2 rounded-full bg-accent" />
          <span>Connected</span>
        </div>
      </div>
    </aside>
  );
}
