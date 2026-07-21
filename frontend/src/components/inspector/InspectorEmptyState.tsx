import { Baseline, Layers } from "lucide-react";

interface InspectorEmptyStateProps {
  variant: "no-selection" | "multi-select";
  t?: (key: string) => string;
  reviewProblemCount?: number;
  onNextProblem?: () => void;
}

export function InspectorEmptyState({
  variant,
  reviewProblemCount = 0,
  onNextProblem,
  t = (key) => key,
}: InspectorEmptyStateProps) {
  const isMultiSelect = variant === "multi-select";
  const Icon = isMultiSelect ? Layers : Baseline;

  return (
    <aside className={`inspector-container empty ${isMultiSelect ? "multi-select" : ""}`}>
      <div className="empty-state-visual">
        <Icon size={36} className="empty-icon" />
        <div className="glow-effect" />
      </div>
      <h3 className="empty-title">{isMultiSelect ? t("inspector.multiSelect") : t("inspector.noSelection")}</h3>
      <p className="empty-desc">
        {isMultiSelect
          ? t("inspector.multiSelectDesc")
          : t("inspector.noSelectionDesc")}
      </p>
      {!isMultiSelect && reviewProblemCount > 0 && onNextProblem && (
        <button type="button" className="empty-review-button" onClick={onNextProblem}>
          <span>{t("inspector.reviewProblems").replace("{count}", String(reviewProblemCount))}</span>
        </button>
      )}
      <style>{`
        .inspector-container.empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          text-align: center;
          padding: 40px 24px;
          color: var(--text-secondary);
          font-size: 13px;
          background-color: var(--bg-inspector);
          border-left: 1px solid var(--border-color);
          width: var(--inspector-width);
        }
        .empty-state-visual {
          position: relative;
          margin-bottom: 16px;
          display: flex;
          align-items: center;
          justify-content: center;
          width: 80px;
          height: 80px;
        }
        .empty-icon {
          color: var(--system-blue);
          opacity: 0.8;
          z-index: 2;
        }
        .glow-effect {
          position: absolute;
          width: 60px;
          height: 60px;
          background: radial-gradient(circle, rgba(10, 132, 255, 0.2) 0%, rgba(10, 132, 255, 0) 70%);
          border-radius: 50%;
          z-index: 1;
        }
        .empty-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 6px;
        }
        .empty-desc {
          font-size: 12px;
          color: var(--text-secondary);
          line-height: 1.5;
          margin-bottom: 0;
          padding: 0 10px;
        }
        .inspector-container.empty.multi-select .empty-desc {
          margin-bottom: 24px;
        }
        .empty-review-button {
          min-height: 34px;
          margin-top: 16px;
          padding: 0 12px;
          border: 1px solid var(--accent-border-subtle);
          border-radius: var(--radius-md);
          background: var(--accent-bg-subtle);
          color: var(--system-blue);
          font: 650 11.5px/1 var(--font-family);
          cursor: pointer;
        }
        .empty-review-button:hover {
          background: color-mix(in srgb, var(--system-blue) 13%, transparent);
        }
        .empty-help-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          text-align: left;
          width: 100%;
          max-width: 200px;
        }
        .help-item {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 11px;
          color: var(--text-tertiary);
        }
        .help-item .bullet {
          color: var(--system-blue);
          font-weight: bold;
        }
      `}</style>
    </aside>
  );
}
