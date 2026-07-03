// frontend/src/components/Canvas.tsx
import React, { useRef, useState } from "react";
import type { BubbleInfo } from "../types";
import { CanvasTranslateButton } from "./canvas/CanvasTranslateButton";
import { CanvasMultiSelectEmpty } from "./canvas/CanvasMultiSelectEmpty";
import { CanvasImageStage } from "./canvas/CanvasImageStage";
import { useCanvasKeyboardGuards } from "./canvas/useCanvasKeyboardGuards";
import { useCanvasImageLoader } from "./canvas/useCanvasImageLoader";
import { useCanvasViewport } from "./canvas/useCanvasViewport";
import { useBubbleDrag } from "./canvas/useBubbleDrag";

interface CanvasProps {
  imageUrl: string;
  fullResImageUrl?: string;
  imageWidth?: number;
  imageHeight?: number;
  pageIndex: number;
  bubbles: BubbleInfo[];
  selectedBubbleId: number | null;
  onSelectBubble: (id: number | null) => void;
  onPreviewBubbles: (updated: BubbleInfo[]) => void;
  onUpdateBubbles: (updated: BubbleInfo[]) => void;
  onTranslate: () => void;
  isProcessing: boolean;
  onDeleteBubble: (id: number) => void;
  onImageLoaded?: () => void;
  isMultiPageSelection?: boolean;
  selectedPageCount?: number;
  /** When true, page image is reloading — keep existing bubble overlay until new bubbles load. */
  isWaitingForImageReload?: boolean;
}

export const Canvas: React.FC<CanvasProps> = ({
  imageUrl,
  fullResImageUrl,
  imageWidth,
  imageHeight,
  pageIndex,
  bubbles,
  selectedBubbleId,
  onSelectBubble,
  onPreviewBubbles,
  onUpdateBubbles,
  onTranslate,
  isProcessing,
  onDeleteBubble,
  onImageLoaded,
  isMultiPageSelection,
  selectedPageCount,
  isWaitingForImageReload,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Tracks whether the user has manually zoomed/panned the current page, so
  // that container resizes don't reset their view.
  const hasUserAdjustedRef = useRef<boolean>(false);
  const {
    displayImageUrl,
    imageDimensions,
    isImageLoading,
    setImageDimensions,
    handleImageLoad,
    handleImageError,
  } = useCanvasImageLoader({
    containerRef,
    imageRef,
    imageUrl,
    fullResImageUrl,
    imageWidth,
    imageHeight,
    pageIndex,
    scale,
    setScale,
    setPan,
    hasUserAdjustedRef,
    onImageLoaded,
  });
  const {
    handleWheel,
    isPanning,
    isSpacePressed,
    setIsSpacePressed,
    startCanvasPan,
    updateCanvasPan,
    finishCanvasPan,
  } = useCanvasViewport({
    containerRef,
    imageRef,
    imageWidth,
    imageHeight,
    imageDimensions,
    setImageDimensions,
    isImageLoading,
    scale,
    setScale,
    pan,
    setPan,
    hasUserAdjustedRef,
  });

  const {
    draggingBubble,
    draggingBubbleRef,
    finishBubbleDrag,
    setDraggingBubble,
    startBubbleDrag,
    updateBubbleDrag,
  } = useBubbleDrag({
    imageRef,
    imageDimensions,
    scale,
    bubbles,
    onSelectBubble,
    onPreviewBubbles,
    onUpdateBubbles,
  });

  useCanvasKeyboardGuards({
    draggingBubbleRef,
    setDraggingBubble,
    setIsSpacePressed,
    selectedBubbleId,
    bubbles,
    onPreviewBubbles,
    onDeleteBubble,
  });

  const handleMouseDown = (e: React.MouseEvent) => {
    if (draggingBubble !== null) {
      e.preventDefault();
      return;
    }

    if (startCanvasPan(e)) return;

    onSelectBubble(null);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (updateCanvasPan(e)) return;

    updateBubbleDrag(e);
  };

  const handleMouseUp = () => {
    if (finishCanvasPan()) return;

    if (draggingBubble) {
      finishBubbleDrag();
    }
  };

  return (
    <div 
      className="canvas-container" 
      ref={containerRef}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onContextMenu={(e) => e.preventDefault()}
      style={{ cursor: isSpacePressed || isPanning ? "grab" : "default" }}
    >
      {isMultiPageSelection ? (
        <CanvasMultiSelectEmpty selectedPageCount={selectedPageCount} />
      ) : (
        <CanvasImageStage
          displayImageUrl={displayImageUrl}
          imageRef={imageRef}
          imageDimensions={imageDimensions}
          pan={pan}
          scale={scale}
          isImageLoading={isImageLoading}
          bubbles={bubbles}
          selectedBubbleId={selectedBubbleId}
          isWaitingForImageReload={isWaitingForImageReload}
          onImageLoad={handleImageLoad}
          onImageError={handleImageError}
          onStartBubbleDrag={startBubbleDrag}
        />
      )}

      {/* Floating control bar */}
      {displayImageUrl && (
        <div className="canvas-floating-controls">
          <div className="actions-capsule">
            <CanvasTranslateButton
              isProcessing={isProcessing}
              isMultiPageSelection={isMultiPageSelection}
              selectedPageCount={selectedPageCount}
              onTranslate={onTranslate}
            />
          </div>
        </div>
      )}

      <style>{`
        .canvas-container {
          flex: 1;
          background-color: var(--bg-canvas);
          position: relative;
          overflow: hidden;
          outline: none;
        }

        .canvas-viewport {
          will-change: transform;
          width: max-content;
          height: max-content;
        }

        .canvas-image-wrapper {
          box-shadow: var(--shadow-lg);
          background: #ffffff;
          position: relative;
        }

        .canvas-image {
          display: block;
          max-width: none;
          max-height: none;
        }

        .canvas-svg-overlay, .canvas-text-overlay {
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
        }

        .bubble-text-box {
          pointer-events: none;
        }

        .canvas-floating-controls {
          position: absolute;
          bottom: 24px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          align-items: center;
          gap: 12px;
          z-index: 5;
        }

        /* Press feedback: every toolbar button dips slightly when pressed. */
        .canvas-floating-controls button:active:not(:disabled) {
          transform: scale(0.92);
        }

        .actions-capsule {
          display: flex;
          align-items: center;
        }

        .actions-capsule button {
          background: transparent;
          border: none;
          color: var(--text-secondary);
          height: 28px;
          padding: 0 16px;
          font-size: 12px;
          font-weight: 500;
          line-height: 1;
          border-radius: 30px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: background 0.3s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.1s ease;
          white-space: nowrap;
        }

        /* Normalize icon box so it doesn't add baseline/descender gap that
           makes the top padding look larger than the bottom. */
        .actions-capsule button svg {
          display: block;
          flex-shrink: 0;
        }

        /* Prevent layout jitter when Translate ↔ Cancel morphs. */
        .actions-capsule button.primary,
        .actions-capsule button.cancel {
          min-width: 90px;
          justify-content: center;
        }

        .actions-capsule button:hover:not(:disabled) {
          background: var(--fill-hover);
          color: var(--text-primary);
        }

        .actions-capsule button.primary {
          background: linear-gradient(
            90deg,
            var(--system-blue) 0%,
            #5ab3ff 40%,
            #a8d8ff 50%,
            #5ab3ff 60%,
            var(--system-blue) 100%
          );
          background-size: 200% 100%;
          background-position: 100% 0;
          color: white;
          box-shadow:
            0 2px 8px rgba(10, 132, 255, 0.4),
            0 1px 2px rgba(10, 132, 255, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.15);
          animation: shimmer-bg 3s ease-in-out infinite;
        }

        /* Smooth icon/label transition when morphing Translate ↔ Cancel */
        .translate-btn-icon,
        .translate-btn-label {
          display: inline-flex;
          align-items: center;
          transition: opacity 0.2s ease, transform 0.2s ease;
        }
        .actions-capsule button.cancel .translate-btn-icon {
          transform: rotate(90deg);
        }

        @keyframes shimmer-bg {
          0% { background-position: 100% 0; }
          100% { background-position: -100% 0; }
        }

        /* Processing state: faded but still shimmering */
        .actions-capsule button.primary.processing {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .actions-capsule button.primary:hover:not(:disabled) {
          background: linear-gradient(
            90deg,
            var(--system-blue-hover) 0%,
            #7ac4ff 40%,
            #b8e4ff 50%,
            #7ac4ff 60%,
            var(--system-blue-hover) 100%
          );
          background-size: 200% 100%;
          box-shadow:
            0 4px 12px rgba(10, 132, 255, 0.5),
            0 1px 3px rgba(10, 132, 255, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.2);
        }

        .actions-capsule button.cancel {
          background: linear-gradient(
            90deg,
            var(--system-red) 0%,
            #ff6b6b 40%,
            #ffb3b3 50%,
            #ff6b6b 60%,
            var(--system-red) 100%
          );
          background-size: 200% 100%;
          background-position: 100% 0;
          color: white;
          box-shadow:
            0 2px 8px rgba(255, 59, 48, 0.4),
            0 1px 2px rgba(255, 59, 48, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.15);
          animation: shimmer-bg 3s ease-in-out infinite;
        }

        /* Keep the resting red even when pointed at (override generic hover). */
        .actions-capsule button.cancel:hover:not(:disabled) {
          background: linear-gradient(
            90deg,
            var(--system-red) 0%,
            #ff7979 40%,
            #ffc2c2 50%,
            #ff7979 60%,
            var(--system-red) 100%
          );
          background-size: 200% 100%;
          color: white;
        }

          .actions-capsule button:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .control-divider {
          width: 1px;
          height: 20px;
          background: var(--separator-strong);
        }

        .canvas-multi-select-empty {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          color: var(--text-secondary);
          user-select: none;
        }

        .multi-select-icon {
          opacity: 0.35;
        }

        .multi-select-count {
          font-size: 16px;
          font-weight: 600;
          font-family: var(--font-family);
        }

        @media (max-width: 1020px) {
          .actions-capsule button span {
            display: none;
          }
          .actions-capsule button {
            padding: 6px 12px;
          }
        }
      `}</style>
    </div>
  );
};
