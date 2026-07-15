import type React from "react";
import type { RefObject } from "react";
import type { BubbleInfo } from "../../types";
import { CanvasBubbleBoxOverlay } from "./CanvasBubbleBoxOverlay";
import { CanvasBubbleTextOverlay } from "./CanvasBubbleTextOverlay";
import { CanvasDetectionOverlay } from "./CanvasDetectionOverlay";

interface CanvasImageStageProps {
  displayImageUrl: string;
  imageRef: RefObject<HTMLImageElement | null>;
  imageDimensions: { w: number; h: number };
  pan: { x: number; y: number };
  scale: number;
  isImageLoading: boolean;
  bubbles: BubbleInfo[];
  selectedBubbleId: number | null;
  isWaitingForImageReload?: boolean;
  onImageLoad: () => void;
  onImageError: () => void;
  onStartBubbleDrag: (event: React.MouseEvent, bubble: BubbleInfo, type: "move" | "resize") => void;
  showDetectionOverlay?: boolean;
}

export function CanvasImageStage({
  displayImageUrl,
  imageRef,
  imageDimensions,
  pan,
  scale,
  isImageLoading,
  bubbles,
  selectedBubbleId,
  isWaitingForImageReload,
  onImageLoad,
  onImageError,
  onStartBubbleDrag,
  showDetectionOverlay = false,
}: CanvasImageStageProps) {
  return (
    <div
      className="canvas-viewport"
      style={{
        transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
        transformOrigin: "0 0",
        opacity: isImageLoading ? 0 : 1,
        transition: isImageLoading ? "none" : "opacity 0.15s ease-in-out",
      }}
    >
      {displayImageUrl && (
        <div className="canvas-image-wrapper" style={{ position: "relative" }}>
          <img
            ref={imageRef}
            src={displayImageUrl}
            alt="Manga Page"
            className="canvas-image"
            decoding="async"
            onLoad={onImageLoad}
            onError={onImageError}
            draggable={false}
            style={{
              width: imageDimensions.w ? `${imageDimensions.w}px` : undefined,
              height: imageDimensions.h ? `${imageDimensions.h}px` : undefined,
            }}
          />

          {!isWaitingForImageReload && (
            <CanvasBubbleBoxOverlay
              bubbles={bubbles}
              selectedBubbleId={selectedBubbleId}
              scale={scale}
              width={imageDimensions.w || "100%"}
              height={imageDimensions.h || "100%"}
              onStartBubbleDrag={onStartBubbleDrag}
            />
          )}

          {!isWaitingForImageReload && (
            <CanvasBubbleTextOverlay bubbles={bubbles} selectedBubbleId={selectedBubbleId} />
          )}

          {!isWaitingForImageReload && showDetectionOverlay && (
            <CanvasDetectionOverlay bubbles={bubbles} scale={scale} />
          )}
        </div>
      )}
    </div>
  );
}
