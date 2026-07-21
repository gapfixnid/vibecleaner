import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
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

function draftFontSize(bubble: BubbleInfo, settings: Settings): number {
  return bubble.font_size || bubble.computed_font_size || settings.default_font_size || 18;
}

interface PendingSave {
  bubble: BubbleInfo;
  text: string;
  translated: string;
}

export function useBubbleEditing({
  selectedBubble,
  settings,
  onUpdateBubble,
}: UseBubbleEditingOptions) {
  const [syncedBubbleId, setSyncedBubbleId] = useState<number | null>(selectedBubble?.id ?? null);
  const [origText, setOrigText] = useState(selectedBubble?.text || "");
  const [transText, setTransText] = useState(selectedBubble?.translated || "");
  const [fontSizeDraft, setFontSizeDraft] = useState<number>(
    selectedBubble ? draftFontSize(selectedBubble, settings) : 18
  );
  const [colorDraft, setColorDraft] = useState<string>(selectedBubble?.color || "#000000");

  // Tracks the last bubble object this hook rendered with, so that when the
  // selection changes we can capture what needs saving on the bubble we're
  // leaving (see the reset block below).
  const lastBubbleRef = useRef<BubbleInfo | null>(selectedBubble);
  // Any edit that needs to be flushed to the PREVIOUSLY selected bubble,
  // captured synchronously during render and flushed in a layout effect
  // (see comment below for why this can't just be a useEffect).
  const pendingSaveRef = useRef<PendingSave | null>(null);

  // Reset the draft fields synchronously during render when the selected
  // bubble changes — NOT via useEffect. Clicking a different bubble on the
  // canvas calls onSelectBubble synchronously inside the mousedown handler,
  // which React re-renders before the event finishes; the browser then fires
  // `blur` on the still-focused textarea as the mousedown's default action.
  // By that point `saveTextEdits` has already been recreated for the NEW
  // bubble (useCallback deps updated on this render). If origText/transText
  // were reset via a useEffect (which only runs after commit, asynchronously
  // relative to that blur), the stale text would get saved onto the newly
  // selected bubble instead. Doing the reset here (React's documented
  // "adjust state during render" pattern) guarantees origText/transText
  // already match the new bubble by the time this render commits, before
  // that blur can fire.
  //
  // Any pending edit on the bubble we're leaving is captured into
  // pendingSaveRef so it isn't silently lost — it gets flushed by the
  // layout effect below, which (being synchronous) also completes before
  // the browser's blur fires.
  const currentId = selectedBubble?.id ?? null;
  if (currentId !== syncedBubbleId) {
    // This intentionally uses React's render-time state adjustment pattern so
    // a pending textarea blur cannot write into the newly selected bubble.
    // eslint-disable-next-line react-hooks/refs
    const prevBubble = lastBubbleRef.current;
    if (prevBubble && hasBubbleTextEdits(prevBubble, origText, transText)) {
      // eslint-disable-next-line react-hooks/refs
      pendingSaveRef.current = { bubble: prevBubble, text: origText, translated: transText };
    }
    setSyncedBubbleId(currentId);
    setOrigText(selectedBubble?.text || "");
    setTransText(selectedBubble?.translated || "");
    setFontSizeDraft(selectedBubble ? draftFontSize(selectedBubble, settings) : 18);
    setColorDraft(selectedBubble?.color || "#000000");
  }
  // eslint-disable-next-line react-hooks/refs
  lastBubbleRef.current = selectedBubble;

  // Flush a pending save queued by the reset above. useLayoutEffect runs
  // synchronously right after the DOM is committed — still before the
  // browser proceeds to fire the deferred `blur` for the same mousedown —
  // so this reliably wins the race that a plain useEffect would lose.
  useLayoutEffect(() => {
    const pending = pendingSaveRef.current;
    if (!pending) return;
    pendingSaveRef.current = null;
    onUpdateBubble({ ...pending.bubble, text: pending.text, translated: pending.translated });
  });

  // Re-sync when the SAME bubble's text/style changes from the backend
  // (a re-OCR/re-translate result arriving). This isn't blur-adjacent —
  // it's an async server update — so a deferred effect is safe here, unlike
  // the id-change case above.
  useEffect(() => {
    if (!selectedBubble || selectedBubble.id !== syncedBubbleId) return;
    // Backend results replace all four drafts atomically after the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOrigText(selectedBubble.text || "");
    setTransText(selectedBubble.translated || "");
    setFontSizeDraft(draftFontSize(selectedBubble, settings));
    setColorDraft(selectedBubble.color || "#000000");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
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
    // Defensive: only save if the draft state actually belongs to the
    // currently selected bubble (see the render-time reset comment above).
    if (!selectedBubble || selectedBubble.id !== syncedBubbleId) return;
    if (!hasBubbleTextEdits(selectedBubble, origText, transText)) {
      return;
    }
    onUpdateBubble({
      ...selectedBubble,
      text: origText,
      translated: transText,
    });
  }, [onUpdateBubble, origText, selectedBubble, syncedBubbleId, transText]);

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
