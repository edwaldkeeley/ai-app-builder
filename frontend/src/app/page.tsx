"use client";

import { useEffect, Suspense, useCallback } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAuth } from "@/app/(auth)/contexts/AuthContext";
import { useAppState } from "@/features/layout/hooks/useAppState";
import { useKeyboardShortcuts } from "@/features/layout/hooks/useKeyboardShortcuts";
import { SkeletonSidebar, SkeletonEditor } from "@/components/ui/Skeleton";
import { setEditorSelection } from "@/features/editor/stores/editorSelection";
import EditPopover from "@/features/editor/components/EditPopover";

// Dynamic imports for heavy components — loaded only when needed
const Sidebar = dynamic(() => import("@/features/layout/components/Sidebar"), { ssr: false });
const MainContent = dynamic(() => import("@/features/layout/components/MainContent"), { ssr: false });

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const app = useAppState();

  // Auth guard — redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  // EditPopover submit handler: sets the editor selection, sends the prompt, closes popover
  const handleEditSubmit = useCallback(
    (instruction: string) => {
      const sel = app.editSelection;
      if (sel) {
        setEditorSelection(sel);
        app.handlePrompt(instruction);
        app.handleCloseEditPopover();
      }
    },
    [app],
  );

  // Global keyboard shortcuts
  useKeyboardShortcuts({
    onSave: app.handleSave,
    onEscape: () => app.setShowMobileSidebar(false),
    onToggleSidebar: () => {
      if (app.isMobile) {
        app.setShowMobileSidebar(!app.showMobileSidebar);
      }
    },
    onToggleViewMode: () => {
      app.setViewMode(
        app.viewMode === "preview" ? "code" :
        app.viewMode === "code" ? "split" : "preview"
      );
    },
    onNewProject: () => app.handleCreateProject(),
    onCycleFiles: app.handleCycleFiles,
    onCycleFilesBackward: app.handleCycleFilesBackward,
  });

  if (authLoading) {
    return (
      <div className="h-dvh flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-text-secondary">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null; // Will redirect to /login
  }

  return (
    <div className="h-dvh flex">
      <Suspense fallback={<SkeletonSidebar />}>
        <Sidebar
          projects={app.projects}
          activeProjectId={app.activeProjectId}
          onSelectProject={app.handleSelectProject}
          onNewProject={app.handleCreateProject}
          onDeleteProject={app.handleDeleteProject}
          onRenameProject={app.handleRenameProject}
          creating={app.creating}
          deleting={app.deleting}
          chatMode={app.chatMode}
          chatMessages={app.chatMessages}
          generating={app.generating}
          writingStatus={app.writingStatus}
          onSendPrompt={app.handlePrompt}
          onBackToProjects={app.handleBackToProjects}
          loading={app.loading}
          isMobile={app.isMobile}
          showMobileSidebar={app.showMobileSidebar}
          onCloseMobileSidebar={() => app.setShowMobileSidebar(false)}
          onDuplicateProject={app.handleDuplicateProject}
          onFigmaImportComplete={app.handleFigmaImportComplete}
          onDesignUploadComplete={app.handleDesignUploadComplete}
        />
      </Suspense>

      {/* Mobile hamburger button */}
      {app.isMobile && !app.showMobileSidebar && (
        <button
          onClick={() => app.setShowMobileSidebar(true)}
          className="fixed top-3 left-3 z-30 p-2 rounded-lg bg-surface border border-border shadow-lg text-foreground hover:bg-sidebar transition-colors touch-target"
          style={{ top: "calc(12px + env(safe-area-inset-top, 0px))" }}
          aria-label="Open sidebar"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      )}

      <main className="flex-1 flex flex-col min-w-0">
        <Suspense fallback={<SkeletonEditor />}>
          <MainContent
            loading={app.loading || app.filesLoading}
            error={app.error}
            activeProject={app.activeProject}
            files={app.files}
            onRetry={app.fetchProjects}
            onFilesChange={app.handleFilesChange}
            onSendPrompt={app.handlePrompt}
            generating={app.generating}
            onAddFile={app.handleAddFile}
            onDeleteFile={app.handleDeleteFile}
            onRenameFile={app.handleRenameFile}
            activeFilePath={app.activeFilePath}
            onActiveFileChange={app.setActiveFilePath}
            saveStatus={app.saveStatus}
            viewMode={app.viewMode}
            onViewModeChange={app.setViewMode}
            onFigmaImportComplete={app.handleFigmaImportComplete}
            onDesignUploadComplete={app.handleDesignUploadComplete}
            onCreateFromTemplate={app.handleCreateFromTemplate}
            onEditWithAI={app.handleEditWithAI}
            isMobile={app.isMobile}
            dirtyFiles={app.dirtyFiles}
            framework={app.framework}
            onFrameworkChange={app.handleFrameworkChange}
          />
        </Suspense>
      </main>

      {/* AI Edit popover — appears near Monaco selection on "Edit with AI" */}
      {app.editSelection && (
        <EditPopover
          selection={app.editSelection}
          onClose={app.handleCloseEditPopover}
          onSubmit={handleEditSubmit}
        />
      )}
    </div>
  );
}
