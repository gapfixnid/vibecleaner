// frontend/src/components/Canvas.tsx
import React, { useRef, useState } from "react";
import { Bug, ScanEye } from "lucide-react";
import type { BubbleInfo } from "../types";
import { CanvasTranslateButton } from "./canvas/CanvasTranslateButton";
import { CanvasZoomControls } from "./canvas/CanvasZoomControls";
import { CanvasMultiSelectEmpty } from "./canvas/CanvasMultiSelectEmpty";
import { CanvasImageStage } from "./canvas/CanvasImageStage";
import { CanvasEmptyState } from "./canvas/CanvasEmptyState";
import { useCanvasKeyboardGuards } from "./canvas/useCanvasKeyboardGuards";
import { useCanvasImageLoader } from "./canvas/useCanvasImageLoader";
import { useCanvasViewport } from "./canvas/useCanvasViewport";
import { useBubbleDrag } from "./canvas/useBubbleDrag";

interface CanvasProps {
  imageUrl: string;
  fullResImageUrl?: string;
  originalImageUrl?: string;
  hasProcessedImage?: boolean;
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
  /** True while a backend job is being polled (shows the Cancel morph). */
  isJobActive?: boolean;
  onCancelJob?: () => void;
  onDeleteBubble: (id: number) => void;
  onImageLoaded?: () => void;
  onImportImages: () => void;
  onOpenProject: () => void;
  isMultiPageSelection?: boolean;
  selectedPageCount?: number;
  /** When true, page image is reloading — keep existing bubble overlay until new bubbles load. */
  isWaitingForImageReload?: boolean;
  t?: (key: string) => string;
}

export const Canvas: React.FC<CanvasProps> = ({
  imageUrl,
  fullResImageUrl,
  originalImageUrl,
  hasProcessedImage,
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
  isJobActive,
  onCancelJob,
  onDeleteBubble,
  onImageLoaded,
  onImportImages,
  onOpenProject,
  isMultiPageSelection,
  selectedPageCount,
  isWaitingForImageReload,
  t,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [showDetectionOverlay, setShowDetectionOverlay] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

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
    zoomBy,
    zoomTo,
    fitToWindow,
  } = useCanvasViewport({
    containerRef,
    viewportRef,
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
    zoomBy,
    fitToWindow,
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
      ) : !displayImageUrl ? (
        <CanvasEmptyState onImportImages={onImportImages} onOpenProject={onOpenProject} t={t ?? ((key) => key)} />
      ) : (
        <CanvasImageStage
          ref={viewportRef}
          displayImageUrl={showOriginal && originalImageUrl ? originalImageUrl : displayImageUrl}
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
          showDetectionOverlay={showDetectionOverlay}
          hideOverlays={showOriginal}
        />
      )}

      {/* Floating zoom cluster */}
      {displayImageUrl && !isMultiPageSelection && (
        <CanvasZoomControls
          scale={scale}
          onZoomIn={() => zoomBy(1.25)}
          onZoomOut={() => zoomBy(1 / 1.25)}
          onZoomReset={() => zoomTo(1)}
          onZoomFit={fitToWindow}
          t={t}
        />
      )}

      {/* Floating control bar */}
      {displayImageUrl && (
        <div className="canvas-floating-controls">
          <div className="actions-capsule">
            {originalImageUrl && hasProcessedImage && (
              <button
                type="button"
                className={`canvas-compare-button${showOriginal ? " active" : ""}`}
                onPointerDown={() => setShowOriginal(true)}
                onPointerUp={() => setShowOriginal(false)}
                onPointerLeave={() => setShowOriginal(false)}
                onPointerCancel={() => setShowOriginal(false)}
                onKeyDown={(event) => {
                  if (event.key === " " || event.key === "Enter") setShowOriginal(true);
                }}
                onKeyUp={() => setShowOriginal(false)}
                aria-pressed={showOriginal}
                data-tooltip={t?.("canvas.holdForOriginal") || "Hold to view original"}
                data-tooltip-pos="top"
              >
                <ScanEye size={15} />
                <span>{showOriginal ? (t?.("canvas.viewingOriginal") || "Original") : (t?.("canvas.compare") || "Compare")}</span>
              </button>
            )}
            <button
              type="button"
              className={`canvas-debug-button${showDetectionOverlay ? " active" : ""}`}
              onClick={() => setShowDetectionOverlay((visible) => !visible)}
              title={showDetectionOverlay ? (t?.("canvas.hideDetection") || "Hide detection boxes") : (t?.("canvas.showDetection") || "Show detection boxes")}
              aria-label={showDetectionOverlay ? (t?.("canvas.hideDetection") || "Hide detection boxes") : (t?.("canvas.showDetection") || "Show detection boxes")}
            >
              <Bug size={15} />
            </button>
            <CanvasTranslateButton
              isProcessing={isProcessing}
              isJobActive={isJobActive}
              isMultiPageSelection={isMultiPageSelection}
              selectedPageCount={selectedPageCount}
              onTranslate={onTranslate}
              onCancel={onCancelJob}
              t={t}
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

        .canvas-empty-state {
          position: absolute;
          inset: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 18px;
          padding: 32px;
          text-align: center;
          color: var(--text-primary);
        }

        .canvas-empty-art {
          position: relative;
          width: 92px;
          height: 92px;
          margin-bottom: 2px;
        }

        .canvas-empty-page {
          position: absolute;
          width: 62px;
          height: 78px;
          border: 1px solid var(--separator-strong);
          border-radius: 12px;
          background: var(--bg-panel);
          box-shadow: var(--shadow-md);
        }

        .canvas-empty-page-back {
          top: 3px;
          left: 10px;
          transform: rotate(-8deg);
          opacity: 0.58;
        }

        .canvas-empty-page-front {
          right: 8px;
          bottom: 0;
          display: grid;
          place-items: center;
          color: var(--system-blue);
        }

        .canvas-empty-copy {
          max-width: 420px;
        }

        .canvas-empty-eyebrow {
          margin-bottom: 7px;
          color: var(--system-blue);
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.08em;
        }

        .canvas-empty-copy h1 {
          margin: 0;
          font-size: 21px;
          font-weight: 680;
          letter-spacing: -0.02em;
        }

        .canvas-empty-copy > p:last-child {
          margin-top: 8px;
          color: var(--text-secondary);
          font-size: 13px;
          line-height: 1.55;
        }

        .canvas-empty-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .canvas-empty-actions button {
          min-height: 38px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          padding: 0 15px;
          border-radius: var(--radius-md);
          font: 600 12.5px/1 var(--font-family);
          cursor: pointer;
          transition: background-color var(--transition-fast), border-color var(--transition-fast), transform var(--transition-fast);
        }

        .canvas-empty-actions button:active {
          transform: translateY(1px);
        }

        .canvas-empty-primary {
          border: 1px solid var(--system-blue);
          background: var(--system-blue);
          color: #fff;
          box-shadow: 0 6px 18px color-mix(in srgb, var(--system-blue) 24%, transparent);
        }

        .canvas-empty-primary:hover {
          background: var(--system-blue-hover);
          border-color: var(--system-blue-hover);
        }

        .canvas-empty-secondary {
          border: 1px solid var(--border-color);
          background: var(--bg-panel);
          color: var(--text-primary);
        }

        .canvas-empty-secondary:hover {
          background: var(--fill-hover);
          border-color: var(--separator-strong);
        }

        .canvas-empty-drop-hint {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          color: var(--text-tertiary);
          font-size: 11px;
        }

        .canvas-image-wrapper {
          box-shadow: var(--shadow-lg);
          background: var(--page-paper);
          position: relative;
        }

        .canvas-image {
          display: block;
          max-width: none;
          max-height: none;
        }

        .canvas-debug-button {
          width: 30px;
          height: 30px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 0;
          border-radius: 9px;
          color: var(--text-secondary);
          background: transparent;
          cursor: pointer;
        }

        .canvas-debug-button:hover, .canvas-debug-button.active {
          color: var(--system-blue);
          background: color-mix(in srgb, var(--system-blue) 14%, transparent);
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
          transition: background var(--transition-slow), color var(--transition-slow), box-shadow var(--transition-slow), transform 0.1s ease;
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
          background: var(--system-blue);
          color: white;
          box-shadow: 0 5px 14px color-mix(in srgb, var(--system-blue) 26%, transparent);
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

        /* Processing state stays calm while progress is shown in the status bar. */
        .actions-capsule button.primary.processing {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .actions-capsule button.primary:hover:not(:disabled) {
          background: var(--system-blue-hover);
          box-shadow: 0 6px 18px color-mix(in srgb, var(--system-blue) 32%, transparent);
        }

        .actions-capsule button.cancel {
          background: var(--system-red);
          color: white;
          box-shadow: 0 5px 14px color-mix(in srgb, var(--system-red) 24%, transparent);
        }

        /* Keep the resting red even when pointed at (override generic hover). */
        .actions-capsule button.cancel:hover:not(:disabled) {
          background: color-mix(in srgb, var(--system-red) 88%, black);
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
