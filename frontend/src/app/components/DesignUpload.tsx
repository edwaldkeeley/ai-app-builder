"use client";

import { useState, useRef } from "react";
import { api } from "../lib/api";
import { useToast } from "./Toast";

interface DesignUploadProps {
  projectId?: string;
  onUploadComplete?: (projectId: string) => void;
  variant?: "landing" | "toolbar" | "inline";
}

const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif", "image/bmp"];
const MAX_SIZE_MB = 10;

export default function DesignUpload({ projectId, onUploadComplete, variant = "landing" }: DesignUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [promptText, setPromptText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setErrorMsg(null);

    if (!file) {
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    // Validate type
    if (!ALLOWED_TYPES.includes(file.type)) {
      setErrorMsg("Unsupported file type. Please upload PNG, JPG, WebP, GIF, or BMP.");
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    // Validate size
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setErrorMsg(`File too large. Maximum size is ${MAX_SIZE_MB} MB.`);
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setErrorMsg(null);

    try {
      // If no projectId, create a new project first
      let targetId = projectId;
      if (!targetId) {
        const newProject = await api.createProject("Design Upload", "Generated from uploaded design image");
        targetId = newProject.id;
      }
      const result = await api.uploadDesign(targetId, selectedFile, promptText.trim() || undefined);
      showToast("success", `Design uploaded — "${result.project_name}" updated`);
      onUploadComplete?.(result.project_id);
      setSelectedFile(null);
      setPreviewUrl(null);
      setPromptText("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setErrorMsg(msg);
      showToast("error", "Failed to upload design");
    } finally {
      setUploading(false);
    }
  };

  // ── Inline variant (compact, for popup menu) ──────────────

  if (variant === "inline") {
    return (
      <div className="p-3 space-y-2">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-accent flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span className="text-xs font-semibold text-foreground">Design Upload</span>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/webp,image/gif,image/bmp"
          onChange={handleFileSelect}
          className="w-full text-xs text-foreground file:mr-2 file:py-1 file:px-2.5 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-accent file:text-white hover:file:bg-accent-hover file:cursor-pointer"
        />
        {previewUrl && (
          <div className="relative w-full h-24 rounded-lg overflow-hidden border border-border bg-background">
            <img src={previewUrl} alt="Design preview" className="w-full h-full object-contain" />
          </div>
        )}
        <input
          type="text"
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          placeholder="Optional prompt..."
          className="w-full bg-input border border-border rounded-lg px-2.5 py-1.5 text-xs text-foreground placeholder-text-secondary outline-none focus:border-accent/50"
        />
        {errorMsg && (
          <p className="text-[10px] text-danger">{errorMsg}</p>
        )}
        <button
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
          className="w-full px-2.5 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? (
            <span className="flex items-center justify-center gap-1.5">
              <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Generating...
            </span>
          ) : (
            "Generate from Image"
          )}
        </button>
      </div>
    );
  }

  // ── Toolbar variant (icon button opens modal) ─────

  if (variant === "toolbar") {
    return (
      <>
        <button
          onClick={() => setShowModal(true)}
          className="p-1.5 rounded-md hover:bg-surface text-text-secondary hover:text-foreground transition-colors"
          title="Upload a design image"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>

        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => { setShowModal(false); setErrorMsg(null); setSelectedFile(null); setPreviewUrl(null); }}>
            <div className="bg-panel border border-border rounded-xl p-5 w-full max-w-md mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Upload Design Image</h3>
                  <p className="text-xs text-text-secondary">Generate code from a screenshot or design mockup</p>
                </div>
              </div>
              <div className="space-y-3">
                {/* File picker */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp,image/gif,image/bmp"
                  onChange={handleFileSelect}
                  className="w-full text-sm text-foreground file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-accent file:text-white hover:file:bg-accent-hover file:cursor-pointer"
                />

                {/* Preview */}
                {previewUrl && (
                  <div className="relative w-full h-40 rounded-lg overflow-hidden border border-border bg-background">
                    <img src={previewUrl} alt="Design preview" className="w-full h-full object-contain" />
                  </div>
                )}

                {/* Optional prompt */}
                <input
                  type="text"
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  placeholder="Optional: describe what to focus on..."
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-text-secondary outline-none focus:border-accent/50"
                />

                {errorMsg && (
                  <p className="text-xs text-danger">{errorMsg}</p>
                )}

                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => { setShowModal(false); setErrorMsg(null); setSelectedFile(null); setPreviewUrl(null); }}
                    className="flex-1 px-3 py-2 text-sm font-medium rounded-lg border border-border text-foreground hover:bg-surface transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleUpload}
                    disabled={!selectedFile || uploading}
                    className="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {uploading ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Generating...
                      </span>
                    ) : (
                      "Generate from Image"
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  // ── Landing page variant ──────────────────────────────────

  return (
    <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-medium text-foreground">Design Upload</h3>
          <p className="text-[11px] text-text-secondary">Upload an image to generate matching code</p>
        </div>
      </div>
      <div className="space-y-2">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/webp,image/gif,image/bmp"
          onChange={handleFileSelect}
          className="w-full text-sm text-foreground file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-accent file:text-white hover:file:bg-accent-hover file:cursor-pointer"
        />
        {previewUrl && (
          <div className="relative w-full h-32 rounded-lg overflow-hidden border border-border bg-background">
            <img src={previewUrl} alt="Design preview" className="w-full h-full object-contain" />
          </div>
        )}
        <input
          type="text"
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          placeholder="Optional: describe what to focus on..."
          className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-text-secondary outline-none focus:border-accent/50"
        />
        {errorMsg && (
          <p className="text-xs text-danger">{errorMsg}</p>
        )}
        <button
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
          className="w-full px-3 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? (
            <span className="flex items-center justify-center gap-2">
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Generating code from image...
            </span>
          ) : (
            "Generate from Image"
          )}
        </button>
      </div>
    </div>
  );
}
