import { X } from "lucide-react";
import type { ActiveJobInfo } from "../hooks/useProcessingTask";
import "./statusbar.css";

interface StatusBarProps {
  activeJob: ActiveJobInfo | null;
  onCancel: () => void;
  pageCount: number;
  /** -1 when no page is selected. */
  currentIndex: number;
  isDirty: boolean;
  t: (key: string) => string;
}

export function StatusBar({ activeJob, onCancel, pageCount, currentIndex, isDirty, t }: StatusBarProps) {
  const jobText = activeJob ? activeJob.message || activeJob.label : t("statusbar.ready");
  const progress = activeJob?.progress ?? null;
  const pageIndicator =
    pageCount > 0 && currentIndex >= 0
      ? t("statusbar.pageIndicator")
          .replace("{n}", String(currentIndex + 1))
          .replace("{total}", String(pageCount))
      : null;

  return (
    <div className="status-bar">
      <div className="status-bar-left">
        <span className="status-bar-text" role="status" aria-live="polite">
          {jobText}
        </span>
        {activeJob && (
          <>
            <span
              className={`status-bar-track ${progress === null ? "indeterminate" : ""}`}
              aria-hidden="true"
            >
              <span
                className="status-bar-fill"
                style={progress !== null ? { width: `${Math.max(2, Math.min(100, progress))}%` } : undefined}
              />
            </span>
            {progress !== null && <span className="status-bar-percent">{Math.round(progress)}%</span>}
            <button
              type="button"
              className="status-bar-cancel"
              onClick={onCancel}
              data-tooltip={t("dialog.cancel")}
              data-tooltip-pos="top"
              aria-label={t("dialog.cancel")}
            >
              <X size={11} />
            </button>
          </>
        )}
      </div>
      <div className="status-bar-right">
        {isDirty && (
          <span className="status-bar-unsaved" title={t("statusbar.unsaved")}>
            <span className="status-bar-unsaved-dot" aria-hidden="true" />
            {t("statusbar.unsaved")}
          </span>
        )}
        {pageIndicator && <span className="status-bar-pages">{pageIndicator}</span>}
      </div>
    </div>
  );
}
