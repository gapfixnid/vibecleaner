import { FolderOpen, ImagePlus, MoveDown } from "lucide-react";

interface CanvasEmptyStateProps {
  onImportImages: () => void;
  onOpenProject: () => void;
  isBackendReady?: boolean;
  t: (key: string) => string;
}

export function CanvasEmptyState({ onImportImages, onOpenProject, isBackendReady = true, t }: CanvasEmptyStateProps) {
  return (
    <section className="canvas-empty-state" aria-labelledby="canvas-empty-title">
      <div className="canvas-empty-art" aria-hidden="true">
        <div className="canvas-empty-page canvas-empty-page-back" />
        <div className="canvas-empty-page canvas-empty-page-front">
          <ImagePlus size={25} strokeWidth={1.6} />
        </div>
      </div>
      <div className="canvas-empty-copy">
        <p className="canvas-empty-eyebrow">{t("canvas.emptyEyebrow")}</p>
        <h1 id="canvas-empty-title">{t("canvas.emptyTitle")}</h1>
        <p>{t("canvas.emptyDescription")}</p>
      </div>
      <div className="canvas-empty-actions">
        <button
          type="button"
          className="canvas-empty-primary"
          onClick={onImportImages}
          disabled={!isBackendReady}
          aria-busy={!isBackendReady}
        >
          <ImagePlus size={16} />
          <span>{t("toolbar.addImages")}</span>
        </button>
        <button type="button" className="canvas-empty-secondary" onClick={onOpenProject}>
          <FolderOpen size={16} />
          <span>{t("toolbar.openProject")}</span>
        </button>
      </div>
      <div className="canvas-empty-drop-hint">
        <MoveDown size={13} aria-hidden="true" />
        <span>{t("canvas.emptyDropHint")}</span>
      </div>
    </section>
  );
}
