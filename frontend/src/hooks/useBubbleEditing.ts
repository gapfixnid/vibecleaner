import { useCallback, useEffect, useState } from "react";
import type { BubbleInfo, Settings } from "../types";

interface UseBubbleEditingOptions {
  selectedBubble: BubbleInfo | null;
  settings: Settings;
  onUpdateBubble: (updated: BubbleInfo) => void;
}

export function hasBubbleTextEdits(
  selectedBubble: Pick<BubbleInfo, "text" | "translated"> | null,
  origText: string,
  transText: string,
) {
  if (!selectedBubble) return false;
  return origText !== (selectedBubble.text || "") || transText !== (selectedBubble.translated || "");
}

export function shouldUpdateBubbleField(
  selectedBubble: BubbleInfo | null,
  key: keyof BubbleInfo,
  value: BubbleInfo[keyof BubbleInfo],
) {
  if (!selectedBubble) return false;
  return !Object.is(selectedBubble[key], value);
}

export function useBubbleEditing({
  selectedBubble,
  settings,
  onUpdateBubble,
}: UseBubbleEditingOptions) {
  const [origText, setOrigText] = useState("");
  const [transText, setTransText] = useState("");
  const [fontSizeDraft, setFontSizeDraft] = useState<number>(18);
  const [colorDraft, setColorDraft] = useState<string>("#000000");

  useEffect(() => {
    if (selectedBubble) {
      setOrigText(selectedBubble.text || "");
      setTransText(selectedBubble.translated || "");
      setFontSizeDraft(selectedBubble.font_size || selectedBubble.computed_font_size || settings.default_font_size || 18);
      setColorDraft(selectedBubble.color || "#000000");
    }
    // Reset only when switching bubbles or when the bubble's own text/style
    // changes from the backend (re-OCR/translate) — not on every re-render,
    // which would otherwise wipe unsaved keystrokes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    selectedBubble?.id,
    selectedBubble?.text,
    selectedBubble?.translated,
    selectedBubble?.font_size,
    selectedBubble?.computed_font_size,
    selectedBubble?.color,
  ]);

  const updateBubbleField = useCallback(
    (key: keyof BubbleInfo, value: BubbleInfo[keyof BubbleInfo]) => {
      if (!selectedBubble || !shouldUpdateBubbleField(selectedBubble, key, value)) return;
      onUpdateBubble({
        ...selectedBubble,
        [key]: value,
      });
    },
    [onUpdateBubble, selectedBubble],
  );

  const saveTextEdits = useCallback(() => {
    if (!selectedBubble) return;
    if (!hasBubbleTextEdits(selectedBubble, origText, transText)) {
      return;
    }
    onUpdateBubble({
      ...selectedBubble,
      text: origText,
      translated: transText,
    });
  }, [onUpdateBubble, origText, selectedBubble, transText]);

  return {
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
  };
}
