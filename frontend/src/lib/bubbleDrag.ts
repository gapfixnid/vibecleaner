import type { BubbleInfo } from "../types";

export function canStartBubbleDrag(
  selectedBubbleId: number | null,
  bubbleId: number,
  type: "move" | "resize",
): boolean {
  return type === "resize" || selectedBubbleId === bubbleId;
}

export function bubbleGeometryChanged(
  bubble: BubbleInfo,
  initial: { x: number; y: number; width: number; height: number },
): boolean {
  return bubble.x !== initial.x
    || bubble.y !== initial.y
    || bubble.width !== initial.width
    || bubble.height !== initial.height;
}
