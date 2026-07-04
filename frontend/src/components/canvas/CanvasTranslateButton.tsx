import { Sparkles } from "lucide-react";

interface CanvasTranslateButtonProps {
  isProcessing: boolean;
  isMultiPageSelection?: boolean;
  selectedPageCount?: number;
  onTranslate: () => void;
  t?: (key: string) => string;
}

export function CanvasTranslateButton({
  isProcessing,
  isMultiPageSelection,
  selectedPageCount,
  onTranslate,
  t = (key) => key,
}: CanvasTranslateButtonProps) {
  const translateLabel = isProcessing ? t("toolbar.translating") : t("toolbar.translate");
  const translatePagesLabel = t("toolbar.translatePageCount").replace("{count}", String(selectedPageCount ?? 0));
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
