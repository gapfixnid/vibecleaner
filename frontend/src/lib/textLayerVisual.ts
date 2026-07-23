import type { BubbleInfo } from "../types";

export interface SelectionRenderState {
  bubbleId: number | null;
  baselineSignature: string | null;
  baselineMoveSignature: string | null;
  baselineX: number;
  baselineY: number;
  baselineTileKey: string | null;
  editing: boolean;
}

export function bubbleMoveSignature(bubble: BubbleInfo): string {
  return JSON.stringify([
    bubble.text,
    bubble.translated,
    bubble.width,
    bubble.height,
    bubble.font_family,
    bubble.font_size,
    bubble.bold,
    bubble.italic,
    bubble.color,
    bubble.alignment,
    bubble.writing_mode,
    bubble.text_direction,
    bubble.justification,
    bubble.layout_padding,
    bubble.layout_margin,
  ]);
}

export function selectionRenderStateFor(bubble: BubbleInfo | null): SelectionRenderState {
  return {
    bubbleId: bubble?.id ?? null,
    baselineSignature: bubble ? bubbleVisualSignature(bubble) : null,
    baselineMoveSignature: bubble ? bubbleMoveSignature(bubble) : null,
    baselineX: bubble?.x ?? 0,
    baselineY: bubble?.y ?? 0,
    baselineTileKey: bubble?.text_layer?.cache_key ?? null,
    editing: false,
  };
}

export function nextSelectionRenderState(
  current: SelectionRenderState,
  bubble: BubbleInfo | null,
): SelectionRenderState {
  if (current.bubbleId !== (bubble?.id ?? null)) {
    return selectionRenderStateFor(bubble);
  }
  const signature = bubble ? bubbleVisualSignature(bubble) : null;
  if (current.editing && current.baselineSignature === signature) {
    return { ...current, editing: false };
  }
  if (bubble !== null && !current.editing && current.baselineSignature !== signature) {
    return { ...current, editing: true };
  }
  return current;
}

/** Inputs whose change makes the selected bubble require a live SVG preview. */
export function bubbleVisualSignature(bubble: BubbleInfo): string {
  return JSON.stringify([
    bubble.text,
    bubble.translated,
    bubble.x,
    bubble.y,
    bubble.width,
    bubble.height,
    bubble.font_family,
    bubble.font_size,
    bubble.bold,
    bubble.italic,
    bubble.color,
    bubble.alignment,
    bubble.writing_mode,
    bubble.text_direction,
    bubble.justification,
    bubble.layout_padding,
    bubble.layout_margin,
  ]);
}
