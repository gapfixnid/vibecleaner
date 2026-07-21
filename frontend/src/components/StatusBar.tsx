import { X } from "lucide-react";
import type { ActiveJobInfo } from "../hooks/useProcessingTask";
import "./statusbar.css";

interface StatusBarProps {
  activeJob: ActiveJobInfo | null;
  onCancel: () => void;
  pageCount: number;
  /** -1 when no page is selected. */
  currentIndex: number;
  selectedPageCount: number;
  isDirty: boolean;
  t: (key: string) => string;
}

export function StatusBar({ activeJob, onCancel, pageCount, currentIndex, selectedPageCount, isDirty, t }: StatusBarProps) {
  const jobText = activeJob ? activeJob.message || activeJob.label : t("statusbar.ready");
  const progress = activeJob?.progress ?? null;
  const pageIndicator = pageCount > 0 && selectedPageCount > 1
    ? t("statusbar.selectedPageIndicator")
        .replace("{count}", String(selectedPageCount))
        .replace("{total}", String(pageCount))
    : pageCount > 0 && currentIndex >= 0
      ? t("statusbar.pageIndicator")
          .replace("{n}", String(currentIndex + 1))
          .replace("{total}", String(pageCount))
      : null;
  const translationStages = [
    t("statusbar.stageDetect"),
    t("statusbar.stageAnalyze"),
    t("statusbar.stageTranslate"),
    t("statusbar.stageClean"),
    t("statusbar.stageRender"),
  ];
  const activeTranslationStage = progress === null
    ? 0
    : progress < 30
      ? 0
      : progress < 45
        ? 1
        : progress < 60
          ? 2
          : progress < 80
            ? 3
            : 4;

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
        {activeJob?.kind === "page-translation" && (
          <ol className="status-bar-stages" aria-label={jobText}>
            {translationStages.map((stage, index) => (
              <li
                key={stage}
                className={index < activeTranslationStage ? "complete" : index === activeTranslationStage ? "active" : ""}
                aria-current={index === activeTranslationStage ? "step" : undefined}
              >
                <span className="status-stage-dot" aria-hidden="true" />
                <span>{stage}</span>
              </li>
            ))}
          </ol>
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
