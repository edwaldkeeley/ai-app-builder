"use client";

import { useState, useEffect, forwardRef, useImperativeHandle } from "react";
import { api } from "@/app/lib/api";
import Modal from "@/components/ui/Modal";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";
import type { Template } from "@/app/lib/types";

interface TemplateGalleryProps {
  framework: "vanilla" | "react";
  onSelectTemplate: (templateId: string) => void;
}

export interface TemplateGalleryHandle {
  open: () => void;
}

const TemplateGallery = forwardRef<TemplateGalleryHandle, TemplateGalleryProps>(function TemplateGallery(
  { framework, onSelectTemplate },
  ref,
) {
  const [showModal, setShowModal] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatingId, setCreatingId] = useState<string | null>(null);
  const { showToast } = useToast();

  useImperativeHandle(ref, () => ({
    open: () => setShowModal(true),
  }));

  useEffect(() => {
    if (!showModal) return;
    setLoading(true);
    setError(null);
    api.listTemplates()
      .then(setTemplates)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load templates"))
      .finally(() => setLoading(false));
  }, [showModal]);

  const handleUse = async (templateId: string) => {
    setCreatingId(templateId);
    try {
      onSelectTemplate(templateId);
      setShowModal(false);
    } catch {
      showToast("error", "Failed to create project from template");
    } finally {
      setCreatingId(null);
    }
  };

  // Filter templates that support the current framework
  const compatible = templates.filter((t) => t.frameworks.includes(framework));
  const incompatible = templates.filter((t) => !t.frameworks.includes(framework));

  return (
    <Modal open={showModal} onClose={() => setShowModal(false)}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-foreground">Choose a Template</h2>
        <span className="text-xs text-text-secondary bg-surface px-2 py-0.5 rounded-full capitalize">
          {framework}
        </span>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <Spinner className="w-6 h-6" />
        </div>
      )}

      {error && (
        <div className="text-center py-8">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button
            onClick={() => { setError(null); setLoading(true); api.listTemplates().then(setTemplates).catch(setError).finally(() => setLoading(false)); }}
            className="text-xs text-accent hover:text-accent-hover underline"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && compatible.length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-text-secondary">No templates available for the {framework} framework.</p>
          <p className="text-xs text-text-secondary mt-1">Switch to Vanilla in the landing page to see more options.</p>
        </div>
      )}

      {!loading && !error && compatible.length > 0 && (
        <div className="space-y-2 max-h-[50dvh] overflow-y-auto pr-1">
          {compatible.map((tmpl) => (
            <button
              key={tmpl.id}
              onClick={() => handleUse(tmpl.id)}
              disabled={creatingId === tmpl.id}
              className="w-full text-left p-3 rounded-lg border border-border hover:border-accent/40 hover:bg-surface transition-all group disabled:opacity-50"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-foreground group-hover:text-accent transition-colors">
                    {tmpl.name}
                  </div>
                  <div className="text-xs text-text-secondary mt-0.5 line-clamp-2">
                    {tmpl.description}
                  </div>
                </div>
                <span className="text-xs font-medium text-accent ml-3 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  {creatingId === tmpl.id ? "Creating..." : "Use →"}
                </span>
              </div>
              <div className="flex gap-1 mt-2">
                {tmpl.frameworks.map((fw) => (
                  <span
                    key={fw}
                    className={`text-[10px] px-1.5 py-0.5 rounded-full capitalize ${
                      fw === framework
                        ? "bg-accent/10 text-accent"
                        : "bg-surface text-text-secondary"
                    }`}
                  >
                    {fw}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}

      {!loading && !error && incompatible.length > 0 && compatible.length > 0 && (
        <details className="mt-3 pt-3 border-t border-border">
          <summary className="text-xs text-text-secondary cursor-pointer hover:text-foreground transition-colors">
            {incompatible.length} template{incompatible.length > 1 ? "s" : ""} not available for {framework}
          </summary>
          <div className="mt-2 space-y-1">
            {incompatible.map((tmpl) => (
              <div key={tmpl.id} className="text-xs text-text-secondary px-2 py-1 rounded bg-surface">
                {tmpl.name}
              </div>
            ))}
          </div>
        </details>
      )}
    </Modal>
  );
});

export default TemplateGallery;
