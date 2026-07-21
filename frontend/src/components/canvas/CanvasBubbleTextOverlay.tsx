import React from "react";
import type { BubbleInfo } from "../../types";

interface CanvasBubbleTextOverlayProps {
  bubbles: BubbleInfo[];
  selectedBubbleId: number | null;
}

export const CanvasBubbleTextOverlay = React.memo(({ bubbles, selectedBubbleId }: CanvasBubbleTextOverlayProps) => {
  return (
    <div className="canvas-text-overlay" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
      {bubbles.map((bubble) => {
        if (!bubble.translated) return null;
        const isSelected = bubble.id === selectedBubbleId;

        return (
          <div
            key={bubble.id}
            className={`bubble-text-box ${isSelected ? "selected" : ""}`}
            style={{
              position: "absolute",
              left: `${bubble.x}px`,
              top: `${bubble.y}px`,
              width: `${bubble.width}px`,
              height: `${bubble.height}px`,
              overflow: "hidden",
            }}
          >
            {bubble.lines && bubble.lines.map((line, lineIndex) => {
              const left = line.x - bubble.x;
              const top = line.y - bubble.y;
              return (
                <div
                  key={lineIndex}
                  style={{
                    position: "absolute",
                    left: `${left}px`,
                    top: `${top}px`,
                    width: `${line.width}px`,
                    height: `${line.height}px`,
                    fontFamily: bubble.font_family || bubble.computed_font_family || "var(--font-family)",
                    fontSize: `${bubble.font_size === 0 ? bubble.computed_font_size : bubble.font_size}px`,
                    fontWeight: bubble.bold ? "bold" : "normal",
                    fontStyle: bubble.italic ? "italic" : "normal",
                    color: bubble.color || "#000000",
                    textAlign: bubble.alignment as any,
                    lineHeight: `${line.height}px`,
                    whiteSpace: "nowrap",
                    textShadow: "0 0 3px #fff, 0 0 3px #fff, 0 0 2px #fff",
                  }}
                >
                  {line.text}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
});

CanvasBubbleTextOverlay.displayName = "CanvasBubbleTextOverlay";
