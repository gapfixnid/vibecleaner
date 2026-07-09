import { Sparkles, X } from "lucide-react";

interface CanvasTranslateButtonProps {
  isProcessing: boolean;
  /** True while a backend job is actually being polled (cancellable window). */
  isJobActive?: boolean;
  isMultiPageSelection?: boolean;
  selectedPageCount?: number;
  onTranslate: () => void;
  onCancel?: () => void;
  t?: (key: string) => string;
}

export function CanvasTranslateButton({
  isProcessing,
  isJobActive,
  isMultiPageSelection,
  selectedPageCount,
  onTranslate,
  onCancel,
  t = (key) => key,
}: CanvasTranslateButtonProps) {
  const translatePagesLabel = t("toolbar.translatePageCount").replace("{count}", String(selectedPageCount ?? 0));

  // While a job is polling, the button morphs into an active Cancel control.
  if (isJobActive && onCancel) {
    return (
      <button
        className="cancel"
        onClick={onCancel}
        data-tooltip={t("dialog.cancel")}
        data-tooltip-pos="top"
        aria-label={t("dialog.cancel")}
      >
        <span className="translate-btn-icon">
          <X size={14} />
        </span>
        <span className="translate-btn-label">{t("dialog.cancel")}</span>
      </button>
    );
  }

  const translateLabel = isProcessing ? t("toolbar.translating") : t("toolbar.translate");
  const tooltip = isProcessing
    ? t("toolbar.translating")
    : (isMultiPageSelection ? translatePagesLabel : t("toolbar.translateCurrentPage"));

  return (
    <button
      className={isProcessing ? "primary processing" : "primary"}
      onClick={onTranslate}
      disabled={isProcessing}
      data-tooltip={tooltip}
      data-tooltip-pos="top"
      aria-label={t("toolbar.translate")}
    >
      <span className="translate-btn-icon">
        <Sparkles size={14} />
      </span>
      <span className="translate-btn-label">{translateLabel}</span>
    </button>
  );
}
