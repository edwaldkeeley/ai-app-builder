"use client";

import { useState, useEffect, useRef, memo } from "react";
import type { ChatMessage, Project } from "@/app/lib/types";
import type { WritingStatus } from "@/features/chat/hooks/useChat";
import ChatPanel from "@/features/chat/components/ChatPanel";
import ThemeToggle from "@/features/layout/components/ThemeToggle";
import SidebarProjectList from "@/features/layout/components/SidebarProjectList";

interface SidebarProps {
  projects: Project[];
  activeProjectId: string | null;
  onSelectProject: (id: string) => void;
  onNewProject: () => void;
  onDeleteProject: (id: string) => void;
  onDuplicateProject?: (id: string) => void;
  onRenameProject?: (id: string, name: string) => void;
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

const Sidebar = memo(function Sidebar({
  projects,
  activeProjectId,
  onSelectProject,
  onNewProject,
  onDeleteProject,
  onDuplicateProject,
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
  onRenameProject,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(isMobile);
  // Sync collapsed state when transitioning between mobile and desktop
  useEffect(() => {
    if (isMobile) {
      const id = setTimeout(() => setCollapsed(true), 0);
      return () => clearTimeout(id);
    }
  }, [isMobile]);
  // On mobile, collapsed state is derived from showMobileSidebar
  const effectiveCollapsed = isMobile ? !showMobileSidebar : collapsed;
  const sidebarRef = useRef<HTMLDivElement>(null);

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
    first?.focus();
    return () => document.removeEventListener("keydown", handleTab);
  }, [isMobile, showMobileSidebar]);

  // On mobile, render as overlay panel
  const sidebarPanel = (content: React.ReactNode) => {
    if (!isMobile) return <div ref={sidebarRef} className="h-full">{content}</div>;
    if (effectiveCollapsed) return content;
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
  if (effectiveCollapsed) {
    if (isMobile) return null;
    return sidebarPanel(
      <aside id="sidebar-panel" className="flex flex-col items-center py-3 px-1 bg-sidebar border-r border-border">
        <button
          onClick={() => setCollapsed(false)}
          className="p-2 rounded-lg hover:bg-surface text-text-secondary hover:text-foreground transition-colors touch-target"
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
            className="p-2 rounded-lg hover:bg-surface text-text-secondary hover:text-foreground disabled:opacity-40 transition-colors touch-target"
            title="New project"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
          </button>
        )}
        <ThemeToggle variant="icon" />
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
            className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors touch-target"
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
              onClick={() => setCollapsed(true)}
              className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors touch-target"
              title="Collapse sidebar"
              aria-expanded={!effectiveCollapsed}
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
          <ThemeToggle showLabel />
        </div>
      </aside>
    );
  }

  // Project list mode
  return sidebarPanel(
    <SidebarProjectList
      projects={projects}
      activeProjectId={activeProjectId}
      onSelectProject={onSelectProject}
      onNewProject={onNewProject}
      onDeleteProject={onDeleteProject}
      onDuplicateProject={onDuplicateProject}
      onRenameProject={onRenameProject}
      creating={creating}
      deleting={deleting}
      loading={loading}
      isMobile={isMobile}
      onCloseMobileSidebar={onCloseMobileSidebar}
      onCollapse={() => setCollapsed(true)}
    />
  );
});

export default Sidebar;
