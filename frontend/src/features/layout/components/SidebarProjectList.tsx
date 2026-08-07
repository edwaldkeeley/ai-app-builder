"use client";

import { useState, useRef, memo } from "react";
import { useRouter } from "next/navigation";
import type { Project } from "@/app/lib/types";
import { useAuth } from "@/app/(auth)/contexts/AuthContext";
import { useTheme } from "@/features/layout/contexts/ThemeContext";
import { SkeletonSidebar } from "@/components/ui/Skeleton";
import ShortcutsModal from "@/features/layout/components/ShortcutsModal";
import ThemeToggle from "@/features/layout/components/ThemeToggle";

interface SidebarProjectListProps {
  projects: Project[];
  activeProjectId: string | null;
  onSelectProject: (id: string) => void;
  onNewProject: () => void;
  onDeleteProject: (id: string) => void;
  onRenameProject?: (id: string, name: string) => void;
  creating: boolean;
  deleting: string | null;
  loading?: boolean;
  isMobile?: boolean;
  onCloseMobileSidebar?: () => void;
  onCollapse: () => void;
}

const SidebarProjectList = memo(function SidebarProjectList({
  projects,
  activeProjectId,
  onSelectProject,
  onNewProject,
  onDeleteProject,
  onRenameProject,
  creating,
  deleting,
  loading,
  isMobile,
  onCloseMobileSidebar,
  onCollapse,
}: SidebarProjectListProps) {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [renamingProject, setRenamingProject] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const handleDelete = (id: string) => {
    if (confirmDelete === id) {
      setConfirmDelete(null);
      onDeleteProject(id);
    } else {
      setConfirmDelete(id);
    }
  };

  const handleStartRename = (id: string, currentName: string) => {
    setRenamingProject(id);
    setRenameValue(currentName);
    setTimeout(() => renameInputRef.current?.focus(), 0);
  };

  const handleFinishRename = () => {
    const id = renamingProject;
    const name = renameValue.trim();
    setRenamingProject(null);
    setRenameValue("");
    if (id && name && onRenameProject) {
      onRenameProject(id, name);
    }
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleFinishRename();
    } else if (e.key === "Escape") {
      setRenamingProject(null);
      setRenameValue("");
    }
  };

  return (
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
            className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground disabled:opacity-40 transition-colors touch-target"
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
              className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors touch-target"
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
              onClick={onCollapse}
              className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors touch-target"
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
                    {renamingProject === project.id ? (
                      <input
                        ref={renameInputRef}
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onBlur={handleFinishRename}
                        onKeyDown={handleRenameKeyDown}
                        onClick={(e) => e.stopPropagation()}
                        className="flex-1 min-w-0 bg-input border border-accent rounded px-1.5 py-0.5 text-sm text-foreground outline-none"
                      />
                    ) : (
                      <span
                        className="truncate font-medium"
                        onDoubleClick={(e) => {
                          e.stopPropagation();
                          handleStartRename(project.id, project.name);
                        }}
                        title="Double-click to rename"
                      >
                        {project.name}
                      </span>
                    )}
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
        <ThemeToggle showLabel />
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
              <div className="absolute bottom-full left-0 right-0 mb-1 mx-2 z-20 bg-surface border border-border rounded-lg shadow-lg py-1 min-w-[160px]" role="menu">
                <div className="px-3 py-1.5 border-b border-border mb-1">
                  <div className="text-xs font-medium text-foreground truncate">{user?.username || "User"}</div>
                  <div className="text-[10px] text-text-secondary truncate">{user?.email || ""}</div>
                </div>
                <button
                  onClick={() => { setShowUserMenu(false); toggleTheme(); }}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-foreground hover:bg-sidebar transition-colors"
                  role="menuitem"
                >
                  {theme === "dark" ? (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                    </svg>
                  )}
                  {theme === "dark" ? "Light mode" : "Dark mode"}
                </button>
                <button
                  onClick={() => { setShowUserMenu(false); setShowShortcuts(true); }}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-foreground hover:bg-sidebar transition-colors"
                  role="menuitem"
                  title="Ctrl+Shift+P to toggle view mode, Ctrl+Tab to cycle files"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Keyboard shortcuts
                </button>
                <button
                  onClick={() => { setShowUserMenu(false); router.push("/settings"); }}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-foreground hover:bg-sidebar transition-colors"
                  role="menuitem"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Settings
                </button>
                <div className="border-t border-border my-1" />
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-danger hover:bg-danger/10 transition-colors"
                  role="menuitem"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <ShortcutsModal open={showShortcuts} onClose={() => setShowShortcuts(false)} />
    </aside>
  );
});

export default SidebarProjectList;
