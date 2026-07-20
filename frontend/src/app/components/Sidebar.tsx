"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import type { ChatMessage, Project } from "../lib/types";
import type { WritingStatus } from "../hooks/useChat";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
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
  onFigmaImportComplete?: (projectId: string) => void;
  onDesignUploadComplete?: (projectId: string) => void;
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
  showMobileSidebar,
  onCloseMobileSidebar,
  onFigmaImportComplete,
  onDesignUploadComplete,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(isMobile);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuth();

  // Sync collapsed state with showMobileSidebar — hamburger opens, backdrop closes
  useEffect(() => {
    if (!isMobile) return;
    setCollapsed(!showMobileSidebar);
  }, [isMobile, showMobileSidebar]);
  const { theme, toggleTheme } = useTheme();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  // Trap focus inside mobile sidebar overlay
  useEffect(() => {
    if (!isMobile || !showMobileSidebar) return;
    const el = sidebarRef.current;
    if (!el) return;
    const focusable = el.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", handleTab);
    // Focus the first focusable element
    first?.focus();
    return () => document.removeEventListener("keydown", handleTab);
  }, [isMobile, showMobileSidebar]);

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
    // Only show backdrop when sidebar is expanded (not collapsed icon state)
    if (collapsed) return content;
    return (
      <>
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/30 z-40"
          onClick={onCloseMobileSidebar}
          aria-hidden="true"
        />
        {/* Overlay panel */}
        <div ref={sidebarRef} className="fixed inset-y-0 left-0 z-50 shadow-xl max-w-[85vw]" style={{ paddingTop: "env(safe-area-inset-top, 0px)", paddingBottom: "env(safe-area-inset-bottom, 0px)" }}>
          {content}
        </div>
      </>
    );
  };

  // Collapsed state — icon button (hidden on mobile, hamburger button handles it)
  if (collapsed) {
    if (isMobile) return null;
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
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>
      </aside>
    );
  }

  // Chat mode — show chat panel in sidebar
  if (chatMode) {
    return sidebarPanel(
      <aside id="sidebar-panel" className="flex flex-col w-80 bg-sidebar border-r border-border h-full">
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
          <span className="text-sm font-semibold truncate flex-1">
            {projects.find((p) => p.id === activeProjectId)?.name ?? "Chat"}
          </span>
          {/* Close button — only on mobile */}
          {isMobile && (
            <button
              onClick={onCloseMobileSidebar}
              className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
              title="Close sidebar"
              aria-label="Close sidebar"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          {/* Collapse button — desktop only */}
          {!isMobile && (
            <button
              onClick={() => setCollapsed(true)}
              className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
              title="Collapse sidebar"
              aria-expanded={!collapsed}
              aria-controls="sidebar-panel"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
              </svg>
            </button>
          )}
        </div>
        {/* Chat panel fills the rest */}
        <ChatPanel
          messages={chatMessages}
          onSend={onSendPrompt}
          disabled={false}
          generating={generating}
          writingStatus={writingStatus}
          projectId={activeProjectId}
          onFigmaImportComplete={onFigmaImportComplete}
          onDesignUploadComplete={onDesignUploadComplete}
        />
        {/* Theme toggle */}
        <div className="border-t border-border p-2">
          <button
            onClick={toggleTheme}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface transition-colors"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              <svg className="w-4 h-4 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="w-4 h-4 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
            <span className="text-xs text-text-secondary">{theme === "dark" ? "Light mode" : "Dark mode"}</span>
          </button>
        </div>
      </aside>
    );
  }

  // Project list mode
  return sidebarPanel(
    <aside id="sidebar-panel" className="flex flex-col w-72 bg-sidebar border-r border-border h-full">
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
          {/* Close button — only on mobile */}
          {isMobile && (
            <button
              onClick={onCloseMobileSidebar}
              className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
              title="Close sidebar"
              aria-label="Close sidebar"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          {/* Collapse button — desktop only */}
          {!isMobile && (
            <button
              onClick={() => setCollapsed(true)}
              className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
              title="Collapse sidebar"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Project list */}
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5 overscroll-contain">
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

      {/* Bottom section — theme toggle + user menu */}
      <div className="border-t border-border p-2 space-y-1">
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface transition-colors"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? (
            <svg className="w-4 h-4 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="w-4 h-4 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
          <span className="text-xs text-text-secondary">{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>
        <div className="relative">
          <button
            onClick={() => setShowUserMenu((prev) => !prev)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface transition-colors"
          >
            <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center text-xs font-medium text-white flex-shrink-0">
              {user?.username?.charAt(0).toUpperCase() || "?"}
            </div>
            <div className="flex-1 text-left min-w-0">
              <div className="text-xs font-medium text-foreground truncate">{user?.username || "User"}</div>
              <div className="text-[10px] text-text-secondary truncate">{user?.email || ""}</div>
            </div>
          </button>
          {showUserMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowUserMenu(false)}
              />
              <div className="absolute bottom-full left-0 right-0 mb-1 mx-2 z-20 bg-surface border border-border rounded-lg shadow-lg py-1">
                <button
                  onClick={handleLogout}
                  className="w-full text-left px-3 py-1.5 text-xs text-text-secondary hover:text-foreground hover:bg-sidebar transition-colors"
                >
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
