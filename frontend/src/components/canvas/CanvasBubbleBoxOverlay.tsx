import React from "react";
import type { BubbleInfo } from "../../types";

interface CanvasBubbleBoxOverlayProps {
  bubbles: BubbleInfo[];
  selectedBubbleId: number | null;
  scale: number;
  width: number | string;
  height: number | string;
  onStartBubbleDrag: (event: React.MouseEvent, bubble: BubbleInfo, type: "move" | "resize") => void;
}

export const CanvasBubbleBoxOverlay = React.memo(
  ({
    bubbles,
    selectedBubbleId,
    scale,
    width,
    height,
    onStartBubbleDrag,
  }: CanvasBubbleBoxOverlayProps) => {
    return (
      <svg
        className="canvas-svg-overlay"
        width={width}
        height={height}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          pointerEvents: "none",
          overflow: "visible",
        }}
      >
        {bubbles.map((bubble) => {
          const isSelected = bubble.id === selectedBubbleId;
          const statusColor = bubble.translated ? "var(--system-green)" : "var(--system-orange)";
          return (
            <g key={bubble.id}>
              <rect
                x={bubble.x}
                y={bubble.y}
                width={bubble.width}
                height={bubble.height}
                fill="rgba(0, 122, 255, 0.02)"
                stroke={isSelected ? "var(--system-blue)" : statusColor}
                strokeWidth={isSelected ? 3 / scale : 1.8 / scale}
                style={{ pointerEvents: "auto", cursor: "move" }}
                onMouseDown={(event) => onStartBubbleDrag(event, bubble, "move")}
              />

              {isSelected && (
                <circle
                  cx={bubble.x + bubble.width}
                  cy={bubble.y + bubble.height}
                  r={6 / scale}
                  fill="var(--system-blue)"
                  stroke="white"
                  strokeWidth={1 / scale}
                  style={{ pointerEvents: "auto", cursor: "se-resize" }}
                  onMouseDown={(event) => onStartBubbleDrag(event, bubble, "resize")}
                />
              )}
            </g>
          );
        })}
      </svg>
    );
  }
);

CanvasBubbleBoxOverlay.displayName = "CanvasBubbleBoxOverlay";
