import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type React from "react";
import type { BubbleInfo } from "../../types";
import { bubbleGeometryChanged, canStartBubbleDrag } from "../../lib/bubbleDrag";

type BubbleDragType = "move" | "resize";

type DraggingBubble = {
  id: number;
  type: BubbleDragType;
  startX: number;
  startY: number;
  initialX: number;
  initialY: number;
  initialW: number;
  initialH: number;
};

interface UseBubbleDragOptions {
  imageRef: RefObject<HTMLImageElement | null>;
  imageDimensions: { w: number; h: number };
  scale: number;
  bubbles: BubbleInfo[];
  selectedBubbleId: number | null;
  onSelectBubble: (id: number | null) => void;
  onPreviewBubbles: (updated: BubbleInfo[]) => void;
  onUpdateBubbles: (updated: BubbleInfo[]) => void;
}

export function useBubbleDrag({
  imageRef,
  imageDimensions,
  scale,
  bubbles,
  selectedBubbleId,
  onSelectBubble,
  onPreviewBubbles,
  onUpdateBubbles,
}: UseBubbleDragOptions) {
  const [draggingBubble, setDraggingBubble] = useState<DraggingBubble | null>(null);
  const latestDragBubblesRef = useRef<BubbleInfo[] | null>(null);

  const finishBubbleDrag = useCallback(() => {
    if (!draggingBubble) return;
    const committed = latestDragBubblesRef.current;
    latestDragBubblesRef.current = null;
    setDraggingBubble(null);
    const changedBubble = committed?.find((bubble) => bubble.id === draggingBubble.id);
    if (committed && changedBubble && bubbleGeometryChanged(changedBubble, {
      x: draggingBubble.initialX,
      y: draggingBubble.initialY,
      width: draggingBubble.initialW,
      height: draggingBubble.initialH,
    })) {
      onUpdateBubbles(committed);
    }
  }, [draggingBubble, onUpdateBubbles]);

  useEffect(() => {
    if (!draggingBubble) return;
    window.addEventListener("mouseup", finishBubbleDrag);
    return () => window.removeEventListener("mouseup", finishBubbleDrag);
  }, [draggingBubble, finishBubbleDrag]);

  const draggingBubbleRef = useRef(draggingBubble);
  useEffect(() => {
    draggingBubbleRef.current = draggingBubble;
  }, [draggingBubble]);

  const updateBubbleDrag = useCallback(
    (e: React.MouseEvent) => {
      if (!draggingBubble) return false;
      if (!imageRef.current) return true;

      const pointerDeltaX = e.clientX - draggingBubble.startX;
      const pointerDeltaY = e.clientY - draggingBubble.startY;
      const imgWidth = imageDimensions.w || imageRef.current.naturalWidth;
      const imgHeight = imageDimensions.h || imageRef.current.naturalHeight;
      const deltaX = pointerDeltaX / scale;
      const deltaY = pointerDeltaY / scale;

      const updated = bubbles.map((b) => {
        if (b.id !== draggingBubble.id) return b;
        if (draggingBubble.type === "move") {
          return {
            ...b,
            x: Math.max(0, Math.min(imgWidth - b.width, draggingBubble.initialX + deltaX)),
            y: Math.max(0, Math.min(imgHeight - b.height, draggingBubble.initialY + deltaY)),
          };
        }
        return {
          ...b,
          width: Math.max(20, draggingBubble.initialW + deltaX),
          height: Math.max(20, draggingBubble.initialH + deltaY),
        };
      });
      latestDragBubblesRef.current = updated;
      onPreviewBubbles(updated);
      return true;
    },
    [bubbles, draggingBubble, imageDimensions.h, imageDimensions.w, imageRef, onPreviewBubbles, scale],
  );

  const startBubbleDrag = useCallback(
    (e: React.MouseEvent, bubble: BubbleInfo, type: BubbleDragType) => {
      // Left button only; let right/middle clicks fall through (pan/context).
      if (e.button !== 0) return;
      e.stopPropagation();
      onSelectBubble(bubble.id);
      latestDragBubblesRef.current = null;
      if (!canStartBubbleDrag(selectedBubbleId, bubble.id, type)) {
        return;
      }
      setDraggingBubble({
        id: bubble.id,
        type,
        startX: e.clientX,
        startY: e.clientY,
        initialX: bubble.x,
        initialY: bubble.y,
        initialW: bubble.width,
        initialH: bubble.height,
      });
    },
    [onSelectBubble, selectedBubbleId],
  );

  return {
    draggingBubble,
    draggingBubbleRef,
    finishBubbleDrag,
    setDraggingBubble,
    startBubbleDrag,
    updateBubbleDrag,
  };
}
