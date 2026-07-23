import React, { useState } from "react";
import type { RefObject } from "react";
import type { BubbleInfo } from "../../types";
import { CanvasBubbleBoxOverlay } from "./CanvasBubbleBoxOverlay";
import { CanvasBubbleTextLayers } from "./CanvasBubbleTextLayers";
import { CanvasDetectionOverlay } from "./CanvasDetectionOverlay";

interface CanvasImageStageProps {
  displayImageUrl: string;
  originalImageUrl?: string;
  showOriginal?: boolean;
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

export const CanvasImageStage = React.forwardRef<HTMLDivElement, CanvasImageStageProps>(
  (
    {
      displayImageUrl,
      originalImageUrl,
      showOriginal = false,
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
    },
    ref
  ) => {
    const [loadedOriginalUrl, setLoadedOriginalUrl] = useState("");
    const isOriginalVisible = Boolean(
      showOriginal && originalImageUrl && loadedOriginalUrl === originalImageUrl,
    );

    return (
      <div
        className="canvas-viewport"
        ref={ref}
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

            {originalImageUrl && (
              <img
                src={originalImageUrl}
                alt=""
                aria-hidden="true"
                className={`canvas-image canvas-original-image${isOriginalVisible ? " visible" : ""}`}
                decoding="async"
                onLoad={() => setLoadedOriginalUrl(originalImageUrl)}
                draggable={false}
                style={{
                  width: imageDimensions.w ? `${imageDimensions.w}px` : undefined,
                  height: imageDimensions.h ? `${imageDimensions.h}px` : undefined,
                }}
              />
            )}

            {!isOriginalVisible && !isWaitingForImageReload && !showDetectionOverlay && (
              <CanvasBubbleBoxOverlay
                bubbles={bubbles}
                selectedBubbleId={selectedBubbleId}
                scale={scale}
                width={imageDimensions.w || "100%"}
                height={imageDimensions.h || "100%"}
                onStartBubbleDrag={onStartBubbleDrag}
              />
            )}

            {!isOriginalVisible && !isWaitingForImageReload && (
              <CanvasBubbleTextLayers
                bubbles={bubbles}
                selectedBubbleId={selectedBubbleId}
                width={imageDimensions.w || bubbles[0]?.page_width || 1}
                height={imageDimensions.h || bubbles[0]?.page_height || 1}
              />
            )}

            {!isOriginalVisible && !isWaitingForImageReload && showDetectionOverlay && (
              <CanvasDetectionOverlay bubbles={bubbles} scale={scale} />
            )}
          </div>
        )}
      </div>
    );
  }
);

CanvasImageStage.displayName = "CanvasImageStage";
