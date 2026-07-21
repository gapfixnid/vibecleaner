// frontend/src/components/Inspector.tsx
import React, { useState } from "react";
import {
  AlertTriangle,
  Baseline,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Type
} from "lucide-react";
import type { BubbleInfo, Settings } from "../types";
import { useBubbleEditing } from "../hooks/useBubbleEditing";
import { InspectorTextSection } from "./inspector/InspectorTextSection";
import { InspectorStyleSection } from "./inspector/InspectorStyleSection";
import { InspectorProblemsSection } from "./inspector/InspectorProblemsSection";
import { InspectorEmptyState } from "./inspector/InspectorEmptyState";
import "./inspector/inspector.css";

interface InspectorProps {
  selectedBubble: BubbleInfo | null;
  settings: Settings;
  onUpdateBubble: (updated: BubbleInfo) => void;
  onReOcrBubble: (id: number) => void;
  onReTranslateBubble: (id: number) => void;
  isProcessing: boolean;
  isMultiPageSelection?: boolean;
  reviewProblemCount?: number;
  reviewProblemPosition?: number;
  onPreviousProblem?: () => void;
  onNextProblem?: () => void;
  t?: (key: string) => string;
}

export const Inspector: React.FC<InspectorProps> = ({
  selectedBubble,
  settings,
  onUpdateBubble,
  onReOcrBubble,
  onReTranslateBubble,
  isProcessing,
  isMultiPageSelection,
  reviewProblemCount = 0,
  reviewProblemPosition = 0,
  onPreviousProblem,
  onNextProblem,
  t = (key) => key,
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
    return <InspectorEmptyState variant="multi-select" t={t} />;
  }

  if (!selectedBubble) {
    return (
      <InspectorEmptyState
        variant="no-selection"
        reviewProblemCount={reviewProblemCount}
        onNextProblem={onNextProblem}
        t={t}
      />
    );
  }

  return (
    <aside className="inspector-container">
      <div className="inspector-header">
        <div className="inspector-header-title">
          <Baseline size={14} className="header-icon" />
          <span>{t("inspector.header").replace("{id}", String(selectedBubble.id))}</span>
        </div>
        {reviewProblemCount > 0 && (
          <div className="review-navigation" aria-label={t("inspector.reviewQueue")}>
            <span className="review-position">
              <AlertTriangle size={11} />
              {reviewProblemPosition > 0 ? `${reviewProblemPosition}/${reviewProblemCount}` : reviewProblemCount}
            </span>
            <button type="button" onClick={onPreviousProblem} aria-label={`${t("inspector.previousProblem")} (Shift+F8)`}>
              <ChevronLeft size={13} />
            </button>
            <button type="button" onClick={onNextProblem} aria-label={`${t("inspector.nextProblem")} (F8)`}>
              <ChevronRight size={13} />
            </button>
          </div>
        )}
      </div>

      <div className="inspector-segmented-control">
        <button 
          className={`segment-btn ${activeTab === "text" ? "active" : ""}`}
          onClick={() => setActiveTab("text")}
        >
          <Type size={12} />
          <span>{t("inspector.text")}</span>
        </button>
        <button 
          className={`segment-btn ${activeTab === "style" ? "active" : ""}`}
          onClick={() => setActiveTab("style")}
        >
          <Sparkles size={12} />
          <span>{t("inspector.style")}</span>
        </button>
      </div>

      <div className="inspector-scrollable">
        {activeTab === "text" ? (
          <InspectorTextSection
            bubbleId={selectedBubble.id}
            isProcessing={isProcessing}
            origText={origText}
            transText={transText}
            settings={settings}
            onOrigTextChange={setOrigText}
            onTransTextChange={setTransText}
            onSaveTextEdits={saveTextEdits}
            onReOcrBubble={onReOcrBubble}
            onReTranslateBubble={onReTranslateBubble}
            t={t}
          />
        ) : (
          <InspectorStyleSection
            selectedBubble={selectedBubble}
            settings={settings}
            fontSizeDraft={fontSizeDraft}
            colorDraft={colorDraft}
            setFontSizeDraft={setFontSizeDraft}
            setColorDraft={setColorDraft}
            updateBubbleField={updateBubbleField}
            t={t}
          />
        )}
        <InspectorProblemsSection selectedBubble={selectedBubble} t={t} />
      </div>
    </aside>
  );
};
