import { Languages, RefreshCw } from "lucide-react";
import type { Settings } from "../../types";

interface InspectorTextSectionProps {
  bubbleId: number;
  isProcessing: boolean;
  origText: string;
  transText: string;
  settings: Settings;
  onOrigTextChange: (value: string) => void;
  onTransTextChange: (value: string) => void;
  onSaveTextEdits: () => void;
  onReOcrBubble: (id: number) => void;
  onReTranslateBubble: (id: number) => void;
  t?: (key: string) => string;
}

export function InspectorTextSection({
  bubbleId,
  isProcessing,
  origText,
  transText,
  settings,
  onOrigTextChange,
  onTransTextChange,
  onSaveTextEdits,
  onReOcrBubble,
  onReTranslateBubble,
  t = (key) => key,
}: InspectorTextSectionProps) {
  return (
    <>
      <div className="section-panel">
        <div className="section-title">
          <span>{t("inspector.original").replace("{language}", settings.source_language)}</span>
          <button
            className="action-link-btn"
            onClick={() => onReOcrBubble(bubbleId)}
            disabled={isProcessing}
          >
            <RefreshCw size={11} className={isProcessing ? "spin" : ""} />
            <span>{t("inspector.reOcr")}</span>
          </button>
        </div>
        <textarea
          className="apple-textarea"
          value={origText}
          onChange={(e) => onOrigTextChange(e.target.value)}
          onBlur={onSaveTextEdits}
          placeholder={t("inspector.noOriginalText")}
        />
      </div>

      <div className="section-panel">
        <div className="section-title">
          <span>{t("inspector.translation").replace("{language}", settings.target_language)}</span>
          <button
            className="action-link-btn primary"
            onClick={() => onReTranslateBubble(bubbleId)}
            disabled={isProcessing}
          >
            <Languages size={11} />
            <span>{t("toolbar.translate")}</span>
          </button>
        </div>
        <textarea
          className="apple-textarea trans"
          value={transText}
          onChange={(e) => onTransTextChange(e.target.value)}
          onBlur={onSaveTextEdits}
          placeholder={t("inspector.translationPlaceholder")}
        />
      </div>
    </>
  );
}
