import type { BubbleInfo } from "../../types";

interface CanvasDetectionOverlayProps {
  bubbles: BubbleInfo[];
  scale: number;
}

/** Visualizes the boxes produced by detection/OCR without intercepting canvas input. */
export function CanvasDetectionOverlay({ bubbles, scale }: CanvasDetectionOverlayProps) {
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
            {textBox && (
              <rect
                x={textBox.x}
                y={textBox.y}
                width={textBox.width}
                height={textBox.height}
                fill="rgba(239, 68, 68, 0.08)"
                stroke="#ef4444"
                strokeWidth={1.5 / scale}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}
