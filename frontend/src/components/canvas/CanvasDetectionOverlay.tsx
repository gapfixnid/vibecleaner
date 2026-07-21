import React from "react";
import type { BubbleInfo } from "../../types";

interface CanvasDetectionOverlayProps {
  bubbles: BubbleInfo[];
  scale: number;
}

/** Visualizes the boxes produced by detection/OCR without intercepting canvas input. */
export const CanvasDetectionOverlay = React.memo(({ bubbles, scale }: CanvasDetectionOverlayProps) => {
  return (
    <svg
      className="canvas-detection-overlay"
      width="100%"
      height="100%"
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        overflow: "visible",
      }}
      aria-label="Detection overlay"
    >
      {bubbles.map((bubble) => {
        const textBox = bubble.text_box;
        const confidence = bubble.detection_confidence && bubble.detection_confidence > 0
          ? bubble.detection_confidence
          : bubble.layout_confidence;
        const ocrText = (bubble.text || "").trim();
        const ocrWarning = !ocrText ? "OCR empty" : ocrText.length <= 2 ? "OCR short" : "";
        const label = `${bubble.text_class || "text"} · ${confidence > 0 ? confidence.toFixed(2) : "—"}${ocrWarning ? ` · ${ocrWarning}` : ""}`;
        return (
          <g key={`detection-${bubble.id}`}>
            <rect
              x={bubble.x}
              y={bubble.y}
              width={bubble.width}
              height={bubble.height}
              fill="rgba(34, 197, 94, 0.06)"
              stroke="#22c55e"
              strokeWidth={1.5 / scale}
              strokeDasharray={`${4 / scale} ${3 / scale}`}
            />
            <text
              x={bubble.x}
              y={Math.max(12 / scale, bubble.y - 4 / scale)}
              fontSize={12 / scale}
              fill="#16a34a"
              stroke="white"
              strokeWidth={3 / scale}
              paintOrder="stroke"
              fontFamily="sans-serif"
            >
              {`#${bubble.id} ${label}`}
            </text>
            {textBox && (
              <rect
                x={textBox.x}
                y={textBox.y}
                width={textBox.width}
                height={textBox.height}
                fill="rgba(239, 68, 68, 0.08)"
                stroke={ocrWarning ? "#f59e0b" : "#ef4444"}
                strokeWidth={1.5 / scale}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
});

CanvasDetectionOverlay.displayName = "CanvasDetectionOverlay";
