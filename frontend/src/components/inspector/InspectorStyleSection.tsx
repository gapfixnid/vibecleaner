import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  ChevronDown,
  Italic,
} from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import type { BubbleInfo, Settings } from "../../types";

interface InspectorStyleSectionProps {
  selectedBubble: BubbleInfo;
  settings: Settings;
  fontSizeDraft: number;
  colorDraft: string;
  setFontSizeDraft: Dispatch<SetStateAction<number>>;
  setColorDraft: Dispatch<SetStateAction<string>>;
  updateBubbleField: (key: keyof BubbleInfo, value: BubbleInfo[keyof BubbleInfo]) => void;
  t?: (key: string) => string;
}

export function InspectorStyleSection({
  selectedBubble,
  settings,
  fontSizeDraft,
  colorDraft,
  setFontSizeDraft,
  setColorDraft,
  updateBubbleField,
  t = (key) => key,
}: InspectorStyleSectionProps) {
  return (
    <div className="section-panel">
      <div className="section-title-simple">{t("inspector.typographyDesign")}</div>

      <div className="form-row">
        <label className="form-label">{t("inspector.fontFamily")}</label>
        <div className="form-control-right">
          <div className="select-wrapper">
            <select
              className="apple-select"
              value={selectedBubble.font_family || "Pretendard Variable"}
              onChange={(e) => updateBubbleField("font_family", e.target.value)}
            >
              <option value="Pretendard Variable">Pretendard</option>
              <option value="Malgun Gothic">Malgun Gothic</option>
              <option value="Gulim">Gulim</option>
              <option value="Arial">Arial</option>
            </select>
            <ChevronDown size={12} className="select-chevron" />
          </div>
        </div>
      </div>

      <div className="form-row size-row">
        <label className="form-label">{t("inspector.fontSize")}</label>
        <div className="form-control-right font-size-controls" style={{ width: "100%", display: "flex", alignItems: "center", gap: "8px" }}>
          <input
            type="range"
            min={settings.min_font_size || 6}
            max={settings.max_font_size || 48}
            className="apple-slider"
            value={fontSizeDraft}
            onChange={(e) => setFontSizeDraft(parseInt(e.target.value))}
            onMouseUp={() => updateBubbleField("font_size", fontSizeDraft)}
            onKeyUp={() => updateBubbleField("font_size", fontSizeDraft)}
            style={{ flex: 1 }}
          />
          <span className="size-indicator" style={{ minWidth: "48px", textAlign: "right" }}>
            {fontSizeDraft}px
          </span>
        </div>
      </div>

      <div className="form-row">
        <label className="form-label">{t("inspector.fontStyle")}</label>
        <div className="form-control-right">
          <div className="style-buttons-group">
            <button
              className={`style-toggle-btn ${selectedBubble.bold ? "active" : ""}`}
              onClick={() => updateBubbleField("bold", !selectedBubble.bold)}
              data-tooltip={t("inspector.bold")}
              aria-label={t("inspector.bold")}
              aria-pressed={selectedBubble.bold}
            >
              <Bold size={13} />
            </button>
            <button
              className={`style-toggle-btn ${selectedBubble.italic ? "active" : ""}`}
              onClick={() => updateBubbleField("italic", !selectedBubble.italic)}
              data-tooltip={t("inspector.italic")}
              aria-label={t("inspector.italic")}
              aria-pressed={selectedBubble.italic}
            >
              <Italic size={13} />
            </button>
          </div>
        </div>
      </div>

      <div className="form-row">
        <label className="form-label">{t("inspector.alignment")}</label>
        <div className="form-control-right">
          <div className="align-buttons-group">
            <button
              className={`align-btn ${selectedBubble.alignment === "left" ? "active" : ""}`}
              onClick={() => updateBubbleField("alignment", "left")}
              data-tooltip={t("inspector.alignLeft")}
              aria-label={t("inspector.alignLeft")}
              aria-pressed={selectedBubble.alignment === "left"}
            >
              <AlignLeft size={13} />
            </button>
            <button
              className={`align-btn ${selectedBubble.alignment === "center" ? "active" : ""}`}
              onClick={() => updateBubbleField("alignment", "center")}
              data-tooltip={t("inspector.alignCenter")}
              aria-label={t("inspector.alignCenter")}
              aria-pressed={selectedBubble.alignment === "center"}
            >
              <AlignCenter size={13} />
            </button>
            <button
              className={`align-btn ${selectedBubble.alignment === "right" ? "active" : ""}`}
              onClick={() => updateBubbleField("alignment", "right")}
              data-tooltip={t("inspector.alignRight")}
              aria-label={t("inspector.alignRight")}
              aria-pressed={selectedBubble.alignment === "right"}
            >
              <AlignRight size={13} />
            </button>
          </div>
        </div>
      </div>

      <div className="form-row">
        <label className="form-label">{t("inspector.textColor")}</label>
        <div className="form-control-right color-picker-row">
          <input
            type="color"
            className="apple-color-picker"
            value={colorDraft}
            onChange={(e) => setColorDraft(e.target.value)}
            onBlur={() => updateBubbleField("color", colorDraft)}
          />
          <span className="color-hex-text">{colorDraft}</span>
        </div>
      </div>

      <div className="form-row border-top-row">
        <label className="form-label">{t("inspector.category")}</label>
        <div className="form-control-right text-right">
          <span className="text-class-badge">{selectedBubble.text_class || "unknown"}</span>
        </div>
      </div>
    </div>
  );
}
