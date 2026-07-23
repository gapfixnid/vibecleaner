import type { BubbleInfo } from "../types";

export interface SelectionRenderState {
  bubbleId: number | null;
  baselineSignature: string | null;
  editing: boolean;
}

export function nextSelectionRenderState(
  current: SelectionRenderState,
  bubbleId: number | null,
  signature: string | null,
): SelectionRenderState {
  if (current.bubbleId !== bubbleId) {
    return { bubbleId, baselineSignature: signature, editing: false };
  }
  if (bubbleId !== null && !current.editing && current.baselineSignature !== signature) {
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
