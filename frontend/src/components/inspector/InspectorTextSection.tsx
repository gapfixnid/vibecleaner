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
}: InspectorTextSectionProps) {
  return (
    <>
      <div className="section-panel">
        <div className="section-title">
          <span>Original ({settings.source_language})</span>
          <button
            className="action-link-btn"
            onClick={() => onReOcrBubble(bubbleId)}
            disabled={isProcessing}
          >
            <RefreshCw size={11} className={isProcessing ? "spin" : ""} />
            <span>Re-OCR</span>
          </button>
        </div>
        <textarea
          className="apple-textarea"
          value={origText}
          onChange={(e) => onOrigTextChange(e.target.value)}
          onBlur={onSaveTextEdits}
          placeholder="No original text detected."
        />
      </div>

      <div className="section-panel">
        <div className="section-title">
          <span>Translation ({settings.target_language})</span>
          <button
            className="action-link-btn primary"
            onClick={() => onReTranslateBubble(bubbleId)}
            disabled={isProcessing}
          >
            <Languages size={11} />
            <span>Translate</span>
          </button>
        </div>
        <textarea
          className="apple-textarea trans"
          value={transText}
          onChange={(e) => onTransTextChange(e.target.value)}
          onBlur={onSaveTextEdits}
          placeholder="Translation result will show here..."
        />
      </div>
    </>
  );
}
