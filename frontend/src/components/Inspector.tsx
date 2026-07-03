// frontend/src/components/Inspector.tsx
import React, { useState } from "react";
import {
  AlignLeft,
  AlignCenter,
  AlignRight,
  Bold,
  Italic,
  RefreshCw,
  Languages,
  Baseline,
  ChevronDown,
  Sparkles,
  Type,
  Layers
} from "lucide-react";
import type { BubbleInfo, Settings } from "../types";
import { useBubbleEditing } from "../hooks/useBubbleEditing";

interface InspectorProps {
  selectedBubble: BubbleInfo | null;
  settings: Settings;
  onUpdateBubble: (updated: BubbleInfo) => void;
  onReOcrBubble: (id: number) => void;
  onReTranslateBubble: (id: number) => void;
  isProcessing: boolean;
  isMultiPageSelection?: boolean;
}

export const Inspector: React.FC<InspectorProps> = ({
  selectedBubble,
  settings,
  onUpdateBubble,
  onReOcrBubble,
  onReTranslateBubble,
  isProcessing,
  isMultiPageSelection,
}) => {
  const [activeTab, setActiveTab] = useState<"text" | "style">("text");
  const {
    colorDraft,
    fontSizeDraft,
    origText,
    transText,
    saveTextEdits,
    setColorDraft,
    setFontSizeDraft,
    setOrigText,
    setTransText,
    updateBubbleField,
  } = useBubbleEditing({
    selectedBubble,
    settings,
    onUpdateBubble,
  });

  if (isMultiPageSelection) {
    return (
      <aside className="inspector-container empty multi-select">
        <div className="empty-state-visual">
          <Layers size={36} className="empty-icon" />
          <div className="glow-effect" />
        </div>
        <h3 className="empty-title">Multiple Pages Selected</h3>
        <p className="empty-desc">Select a single page to edit bubbles.</p>
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
            margin-bottom: 24px;
            padding: 0 10px;
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

  if (!selectedBubble) {
    return (
      <aside className="inspector-container empty">
        <div className="empty-state-visual">
          <Baseline size={36} className="empty-icon" />
          <div className="glow-effect" />
        </div>
        <h3 className="empty-title">No Selection</h3>
        <p className="empty-desc">Select a speech bubble on the canvas to inspect and edit its properties.</p>
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
        `}</style>
      </aside>
    );
  }

  return (
    <aside className="inspector-container">
      <div className="inspector-header">
        <Baseline size={14} className="header-icon" />
        <span>Inspector — Bubble #{selectedBubble.id}</span>
      </div>

      <div className="inspector-segmented-control">
        <button 
          className={`segment-btn ${activeTab === "text" ? "active" : ""}`}
          onClick={() => setActiveTab("text")}
        >
          <Type size={12} />
          <span>Text</span>
        </button>
        <button 
          className={`segment-btn ${activeTab === "style" ? "active" : ""}`}
          onClick={() => setActiveTab("style")}
        >
          <Sparkles size={12} />
          <span>Style</span>
        </button>
      </div>

      <div className="inspector-scrollable">
        {activeTab === "text" ? (
          <>
            {/* original text (Japanese) */}
            <div className="section-panel">
              <div className="section-title">
                <span>Original ({settings.source_language})</span>
                <button 
                  className="action-link-btn" 
                  onClick={() => onReOcrBubble(selectedBubble.id)}
                  disabled={isProcessing}
                >
                  <RefreshCw size={11} className={isProcessing ? "spin" : ""} />
                  <span>Re-OCR</span>
                </button>
              </div>
              <textarea
                className="apple-textarea"
                value={origText}
                onChange={(e) => setOrigText(e.target.value)}
                onBlur={saveTextEdits}
                placeholder="No original text detected."
              />
            </div>

            {/* Translation text (Korean) */}
            <div className="section-panel">
              <div className="section-title">
                <span>Translation ({settings.target_language})</span>
                <button 
                  className="action-link-btn primary" 
                  onClick={() => onReTranslateBubble(selectedBubble.id)}
                  disabled={isProcessing}
                >
                  <Languages size={11} />
                  <span>Translate</span>
                </button>
              </div>
              <textarea
                className="apple-textarea trans"
                value={transText}
                onChange={(e) => setTransText(e.target.value)}
                onBlur={saveTextEdits}
                placeholder="Translation result will show here..."
              />
            </div>
          </>
        ) : (
          /* Typography and styling settings */
          <div className="section-panel">
            <div className="section-title-simple">Typography & Design</div>
            
            <div className="form-row">
              <label className="form-label">Font Family</label>
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
              <label className="form-label">Font Size</label>
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
              <label className="form-label">Font Style</label>
              <div className="form-control-right">
                <div className="style-buttons-group">
                  <button
                    className={`style-toggle-btn ${selectedBubble.bold ? "active" : ""}`}
                    onClick={() => updateBubbleField("bold", !selectedBubble.bold)}
                    data-tooltip="Bold"
                    aria-label="Bold"
                    aria-pressed={selectedBubble.bold}
                  >
                    <Bold size={13} />
                  </button>
                  <button
                    className={`style-toggle-btn ${selectedBubble.italic ? "active" : ""}`}
                    onClick={() => updateBubbleField("italic", !selectedBubble.italic)}
                    data-tooltip="Italic"
                    aria-label="Italic"
                    aria-pressed={selectedBubble.italic}
                  >
                    <Italic size={13} />
                  </button>
                </div>
              </div>
            </div>

            <div className="form-row">
              <label className="form-label">Alignment</label>
              <div className="form-control-right">
                <div className="align-buttons-group">
                  <button
                    className={`align-btn ${selectedBubble.alignment === "left" ? "active" : ""}`}
                    onClick={() => updateBubbleField("alignment", "left")}
                    data-tooltip="Align Left"
                    aria-label="Align left"
                    aria-pressed={selectedBubble.alignment === "left"}
                  >
                    <AlignLeft size={13} />
                  </button>
                  <button
                    className={`align-btn ${selectedBubble.alignment === "center" ? "active" : ""}`}
                    onClick={() => updateBubbleField("alignment", "center")}
                    data-tooltip="Align Center"
                    aria-label="Align center"
                    aria-pressed={selectedBubble.alignment === "center"}
                  >
                    <AlignCenter size={13} />
                  </button>
                  <button
                    className={`align-btn ${selectedBubble.alignment === "right" ? "active" : ""}`}
                    onClick={() => updateBubbleField("alignment", "right")}
                    data-tooltip="Align Right"
                    aria-label="Align right"
                    aria-pressed={selectedBubble.alignment === "right"}
                  >
                    <AlignRight size={13} />
                  </button>
                </div>
              </div>
            </div>

            <div className="form-row">
              <label className="form-label">Text Color</label>
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
              <label className="form-label">Category</label>
              <div className="form-control-right text-right">
                <span className="text-class-badge">{selectedBubble.text_class || "unknown"}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        .inspector-container {
          width: var(--inspector-width);
          border-left: 1px solid var(--border-color);
          background-color: var(--bg-inspector);
          backdrop-filter: var(--glass-blur);
          display: flex;
          flex-direction: column;
          height: 100%;
          user-select: none;
        }

        .inspector-header {
          padding: 14px 16px 12px;
          font-size: 11px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--text-tertiary);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .header-icon {
          color: var(--text-tertiary);
        }

        .inspector-segmented-control {
          display: flex;
          background: var(--inset-bg);
          border-radius: 8px;
          padding: 2px;
          margin: 0 16px 12px;
        }

        .segment-btn {
          flex: 1;
          background: transparent;
          border: none;
          font-size: 11.5px;
          font-weight: 500;
          padding: 6px;
          border-radius: 6px;
          cursor: pointer;
          color: var(--text-secondary);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          transition: all 0.15s cubic-bezier(0.25, 0.8, 0.25, 1);
        }

        .segment-btn:hover {
          color: var(--text-primary);
        }

        .segment-btn.active {
          background: var(--bg-panel);
          color: var(--text-primary);
          box-shadow: var(--shadow-sm);
        }

        .inspector-scrollable {
          flex: 1;
          overflow-y: auto;
          padding: 0 16px 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .section-panel {
          background: var(--fill-4);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-lg);
          padding: 12px;
        }

        .section-title {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--text-secondary);
          margin-bottom: 8px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          letter-spacing: 0.5px;
        }

        .section-title-simple {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--text-secondary);
          margin-bottom: 12px;
          letter-spacing: 0.5px;
        }

        .action-link-btn {
          background: transparent;
          border: none;
          color: var(--system-blue);
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .action-link-btn:hover {
          text-decoration: underline;
        }

        .action-link-btn:disabled {
          opacity: 0.5;
          text-decoration: none;
        }

        .apple-textarea {
          width: 100%;
          height: 90px;
          background: var(--bg-input);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-md);
          color: var(--text-primary);
          padding: 8px;
          font-size: 13px;
          font-family: inherit;
          resize: none;
          outline: none;
          transition: border-color 0.15s;
        }

        .apple-textarea:focus {
          border-color: var(--system-blue);
        }

        .apple-textarea.trans {
          height: 120px;
        }

        .form-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .form-row.border-top-row {
          border-top: 1px solid var(--border-color);
          margin-top: 12px;
          padding-top: 12px;
          margin-bottom: 0;
        }

        .form-label {
          font-size: 12px;
          font-weight: 500;
          color: var(--text-secondary);
          flex: 1.2;
          text-align: left;
        }

        .form-control-right {
          flex: 2;
          display: flex;
          justify-content: flex-end;
          align-items: center;
        }

        .text-right {
          justify-content: flex-end;
        }

        .select-wrapper {
          position: relative;
          width: 100%;
        }

        .apple-select {
          width: 100%;
          background: var(--bg-input);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-md);
          color: var(--text-primary);
          padding: 6px 24px 6px 10px;
          font-size: 12px;
          appearance: none;
          -webkit-appearance: none;
          outline: none;
          cursor: pointer;
        }

        .select-chevron {
          position: absolute;
          right: 8px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--text-secondary);
          pointer-events: none;
        }

        .font-size-controls {
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
        }

        .apple-slider {
          flex: 1;
          accent-color: var(--system-blue);
          height: 4px;
          border-radius: 2px;
          background: var(--separator-strong);
          cursor: pointer;
        }

        .size-indicator {
          font-size: 11px;
          font-weight: 600;
          min-width: 32px;
          text-align: right;
        }

        .style-buttons-group, .align-buttons-group {
          display: flex;
          background: var(--bg-input);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-md);
          padding: 2px;
          gap: 2px;
        }

        .style-toggle-btn, .align-btn {
          background: transparent;
          border: none;
          color: var(--text-secondary);
          width: 24px;
          height: 24px;
          border-radius: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.15s;
        }

        .style-toggle-btn:hover, .align-btn:hover {
          color: var(--text-primary);
        }

        .style-toggle-btn.active, .align-btn.active {
          background: var(--bg-panel);
          color: var(--text-primary);
          box-shadow: var(--shadow-sm);
        }

        .color-picker-row {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .apple-color-picker {
          border: none;
          background: none;
          width: 24px;
          height: 24px;
          cursor: pointer;
          border-radius: 50%;
          overflow: hidden;
          padding: 0;
        }

        .color-hex-text {
          font-size: 11px;
          font-weight: 500;
          font-family: monospace;
          background: var(--bg-input);
          padding: 3px 6px;
          border-radius: 4px;
        }

        .text-class-badge {
          display: inline-block;
          font-size: 9px;
          font-weight: 700;
          text-transform: uppercase;
          background: rgba(255,255,255,0.06);
          color: var(--text-secondary);
          padding: 2px 6px;
          border-radius: 8px;
          border: 1px solid var(--border-color);
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .spin {
          animation: spin 1s linear infinite;
        }
      `}</style>
    </aside>
  );
};
