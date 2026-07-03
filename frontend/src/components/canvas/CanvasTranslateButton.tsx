import { Sparkles } from "lucide-react";

interface CanvasTranslateButtonProps {
  isProcessing: boolean;
  isMultiPageSelection?: boolean;
  selectedPageCount?: number;
  onTranslate: () => void;
}

export function CanvasTranslateButton({
  isProcessing,
  isMultiPageSelection,
  selectedPageCount,
  onTranslate,
}: CanvasTranslateButtonProps) {
  return (
    <button
      className={isProcessing ? "primary processing" : "primary"}
      onClick={onTranslate}
      disabled={isProcessing}
      data-tooltip={isProcessing ? "Translating..." : (isMultiPageSelection ? `Translate ${selectedPageCount} pages` : "Translate current page")}
      data-tooltip-pos="top"
      aria-label="Translate"
    >
      <span className="translate-btn-icon">
        <Sparkles size={14} />
      </span>
      <span className="translate-btn-label">{isProcessing ? "Translating..." : "Translate"}</span>
    </button>
  );
}
