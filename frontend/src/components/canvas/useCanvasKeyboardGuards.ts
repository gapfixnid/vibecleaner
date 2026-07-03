import { useEffect, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import type { BubbleInfo } from "../../types";

interface DraggingBubbleState {
  id: number;
  type: "move" | "resize";
  startX: number;
  startY: number;
  initialX: number;
  initialY: number;
  initialW: number;
  initialH: number;
}

interface UseCanvasKeyboardGuardsDeps {
  draggingBubbleRef: MutableRefObject<DraggingBubbleState | null>;
  setDraggingBubble: Dispatch<SetStateAction<DraggingBubbleState | null>>;
  setIsSpacePressed: Dispatch<SetStateAction<boolean>>;
  selectedBubbleId: number | null;
  bubbles: BubbleInfo[];
  onPreviewBubbles: (updated: BubbleInfo[]) => void;
  onDeleteBubble: (id: number) => void;
}

export function useCanvasKeyboardGuards({
  draggingBubbleRef,
  setDraggingBubble,
  setIsSpacePressed,
  selectedBubbleId,
  bubbles,
  onPreviewBubbles,
  onDeleteBubble,
}: UseCanvasKeyboardGuardsDeps) {
  useEffect(() => {
    const blockRightClickDuringDrag = (event: MouseEvent) => {
      if (draggingBubbleRef.current !== null && event.button === 2) {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    const blockContextMenuDuringDrag = (event: MouseEvent) => {
      if (draggingBubbleRef.current !== null) {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    window.addEventListener("mousedown", blockRightClickDuringDrag, { capture: true });
    window.addEventListener("mouseup", blockRightClickDuringDrag, { capture: true });
    window.addEventListener("contextmenu", blockContextMenuDuringDrag, { capture: true });

    return () => {
      window.removeEventListener("mousedown", blockRightClickDuringDrag, { capture: true });
      window.removeEventListener("mouseup", blockRightClickDuringDrag, { capture: true });
      window.removeEventListener("contextmenu", blockContextMenuDuringDrag, { capture: true });
    };
  }, [draggingBubbleRef]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code === "Space" && event.target === document.body) {
        event.preventDefault();
        setIsSpacePressed(true);
      }
      if (event.code === "Escape") {
        if (draggingBubbleRef.current !== null) {
          setDraggingBubble(null);
          onPreviewBubbles(bubbles);
          event.preventDefault();
          event.stopPropagation();
        }
        return;
      }
      if (event.code === "Delete") {
        if (selectedBubbleId !== null) {
          const activeTag = document.activeElement?.tagName.toLowerCase();
          const isEditing =
            activeTag === "input" ||
            activeTag === "textarea" ||
            activeTag === "select" ||
            (document.activeElement as HTMLElement | null)?.isContentEditable;
          if (!isEditing) {
            onDeleteBubble(selectedBubbleId);
          }
        }
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") {
        setIsSpacePressed(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [
    draggingBubbleRef,
    setDraggingBubble,
    setIsSpacePressed,
    selectedBubbleId,
    onDeleteBubble,
    bubbles,
    onPreviewBubbles,
  ]);
}
