// frontend/src/components/Canvas.tsx
import React, { useRef, useState, useEffect, useLayoutEffect, useCallback } from "react";
import {
  Sparkles,
  Layers
} from "lucide-react";
import type { BubbleInfo } from "../types";

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
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isSpacePressed, setIsSpacePressed] = useState<boolean>(false);
  const [isImageLoading, setIsImageLoading] = useState<boolean>(true);
  const [displayImageUrl, setDisplayImageUrl] = useState<string>(imageUrl);
  const [isUsingFullRes, setIsUsingFullRes] = useState<boolean>(false);
  const [imageDimensions, setImageDimensions] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const fullResRequestRef = useRef<number>(0);
  const fullResPreloadUrlRef = useRef<string>("");

  // Tracks whether the user has manually zoomed/panned the current page, so
  // that container resizes don't reset their view.
  const hasUserAdjustedRef = useRef<boolean>(false);
  const prevPageIndexRef = useRef<number>(-1);

  // Reset loading state and view ONLY when the active page changes. Same-page
  // content changes (inpaint/translate, version bump) swap the image in place
  // without re-centering, which is the desired behavior.
  useEffect(() => {
    if (pageIndex !== prevPageIndexRef.current) {
      setIsImageLoading(true);
      setImageDimensions({ w: 0, h: 0 });
      setScale(1);
      setIsUsingFullRes(false);
      hasUserAdjustedRef.current = false;
      prevPageIndexRef.current = pageIndex;
    }
  }, [pageIndex]);

  useLayoutEffect(() => {
    fullResRequestRef.current += 1;
    fullResPreloadUrlRef.current = "";
    setDisplayImageUrl(imageUrl);
    setIsUsingFullRes(false);
  }, [imageUrl]);

  // Dragging bubble state
  const [draggingBubble, setDraggingBubble] = useState<{
    id: number;
    type: "move" | "resize";
    startX: number;
    startY: number;
    initialX: number;
    initialY: number;
    initialW: number;
    initialH: number;
  } | null>(null);
  const latestDragBubblesRef = useRef<BubbleInfo[] | null>(null);

  const finishBubbleDrag = useCallback(() => {
    if (!draggingBubble) return;
    const committed = latestDragBubblesRef.current;
    latestDragBubblesRef.current = null;
    setDraggingBubble(null);
    if (committed) {
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

  // Prevent right-clicks (button 2) from interrupting active left-click drags
  useEffect(() => {
    const blockRightClickDuringDrag = (e: MouseEvent) => {
      if (draggingBubbleRef.current !== null && e.button === 2) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    const blockContextMenuDuringDrag = (e: MouseEvent) => {
      if (draggingBubbleRef.current !== null) {
        e.preventDefault();
        e.stopPropagation();
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
  }, []);

  // Track key press for spacebar panning
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && e.target === document.body) {
        e.preventDefault();
        setIsSpacePressed(true);
      }
      if (e.code === "Escape") {
        if (draggingBubbleRef.current !== null) {
          setDraggingBubble(null);
          onPreviewBubbles(bubbles);
          e.preventDefault();
          e.stopPropagation();
        }
        return;
      }
      if (e.code === "Delete") {
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

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        setIsSpacePressed(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [selectedBubbleId, onDeleteBubble, bubbles, onPreviewBubbles]);

  // Center image on load
  const handleImageLoad = () => {
    if (!containerRef.current || !imageRef.current) return;
    const containerWidth = containerRef.current.clientWidth;
    const containerHeight = containerRef.current.clientHeight;
    const imgWidth = imageWidth || imageRef.current.naturalWidth;
    const imgHeight = imageHeight || imageRef.current.naturalHeight;

    if (imgWidth > 0 && imgHeight > 0) {
      setImageDimensions({ w: imgWidth, h: imgHeight });
    }

    if (isImageLoading) {
      setIsImageLoading(false);

      if (containerWidth === 0 || containerHeight === 0 || imgWidth === 0 || imgHeight === 0) return;

      const scaleX = (containerWidth - 60) / imgWidth;
      const scaleY = (containerHeight - 60) / imgHeight;
      const initialScale = Math.min(scaleX, scaleY, 1);

      setScale(initialScale);
      setPan({
        x: (containerWidth - imgWidth * initialScale) / 2,
        y: (containerHeight - imgHeight * initialScale) / 2,
      });
    }

    if (onImageLoaded) {
      onImageLoaded();
    }
  };

  const handleImageError = () => {
    if (onImageLoaded) {
      onImageLoaded();
    }
  };

  // Recalculate scale/pan on resize
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      if (!imageRef.current) return;
      const entry = entries[0];
      if (!entry) return;
      
      const containerWidth = entry.contentRect.width;
      const containerHeight = entry.contentRect.height;
      const imgWidth = imageWidth || imageRef.current.naturalWidth;
      const imgHeight = imageHeight || imageRef.current.naturalHeight;

      if (imgWidth === 0 || imgHeight === 0 || containerWidth === 0 || containerHeight === 0) return;

      // Keep dimensions in sync, but preserve the user's zoom/pan: only
      // re-fit when they haven't manually adjusted the view.
      setImageDimensions({ w: imgWidth, h: imgHeight });
      if (hasUserAdjustedRef.current) return;

      const scaleX = (containerWidth - 60) / imgWidth;
      const scaleY = (containerHeight - 60) / imgHeight;
      const initialScale = Math.min(scaleX, scaleY, 1);

      setScale(initialScale);
      setPan({
        x: (containerWidth - imgWidth * initialScale) / 2,
        y: (containerHeight - imgHeight * initialScale) / 2,
      });
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [imageWidth, imageHeight]);

  // Self-correction hook
  useEffect(() => {
    if (isImageLoading || !imageRef.current || !containerRef.current) return;
    
    const imgWidth = imageWidth || imageRef.current.naturalWidth;
    const imgHeight = imageHeight || imageRef.current.naturalHeight;
    const containerWidth = containerRef.current.clientWidth;
    const containerHeight = containerRef.current.clientHeight;

    if (imgWidth === 0 || imgHeight === 0 || containerWidth === 0 || containerHeight === 0) return;

    if (scale === 1 && !hasUserAdjustedRef.current) {
      const scaleX = (containerWidth - 60) / imgWidth;
      const scaleY = (containerHeight - 60) / imgHeight;
      const initialScale = Math.min(scaleX, scaleY, 1);

      setScale(initialScale);
      setPan({
        x: (containerWidth - imgWidth * initialScale) / 2,
        y: (containerHeight - imgHeight * initialScale) / 2,
      });
      setImageDimensions({ w: imgWidth, h: imgHeight });
    }
  }, [isImageLoading, scale, imageWidth, imageHeight]);

  useEffect(() => {
    if (!fullResImageUrl || fullResImageUrl === imageUrl || isUsingFullRes || !imageDimensions.w || !imageDimensions.h) {
      return;
    }

    const maxDimension = Math.max(imageDimensions.w, imageDimensions.h);
    const switchScale = Math.min(1, Math.max(0.5, 1600 / maxDimension));
    if (scale < switchScale) return;
    if (fullResPreloadUrlRef.current === fullResImageUrl) return;

    fullResPreloadUrlRef.current = fullResImageUrl;
    const requestId = ++fullResRequestRef.current;
    const img = new Image();
    img.decoding = "async";
    img.onload = () => {
      if (requestId !== fullResRequestRef.current) return;
      setDisplayImageUrl(fullResImageUrl);
      setIsUsingFullRes(true);
    };
    img.onerror = () => {
      fullResPreloadUrlRef.current = "";
    };
    img.src = fullResImageUrl;
    return () => {
      img.src = "";
    };
  }, [fullResImageUrl, imageUrl, imageDimensions.w, imageDimensions.h, scale, isUsingFullRes]);

  // Zoom on wheel (Ctrl + Wheel)
  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || isSpacePressed) {
      e.preventDefault();
      hasUserAdjustedRef.current = true;
      const zoomFactor = 1.1;
      const nextScale = e.deltaY < 0 ? Math.min(scale * zoomFactor, 5) : Math.max(scale / zoomFactor, 0.15);

      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const imgX = (mouseX - pan.x) / scale;
        const imgY = (mouseY - pan.y) / scale;

        setScale(nextScale);
        setPan({
          x: mouseX - imgX * nextScale,
          y: mouseY - imgY * nextScale,
        });
      }
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (draggingBubble !== null) {
      e.preventDefault();
      return;
    }

    if (isSpacePressed || e.button === 1 || e.button === 2) {
      e.preventDefault();
      hasUserAdjustedRef.current = true;
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
      return;
    }

    onSelectBubble(null);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
      return;
    }

    if (draggingBubble) {
      if (!imageRef.current) return;
      const imgWidth = imageDimensions.w || imageRef.current.naturalWidth;
      const imgHeight = imageDimensions.h || imageRef.current.naturalHeight;
      const deltaX = (e.clientX - draggingBubble.startX) / scale;
      const deltaY = (e.clientY - draggingBubble.startY) / scale;

      const updated = bubbles.map((b) => {
        if (b.id !== draggingBubble.id) return b;
        if (draggingBubble.type === "move") {
          return {
            ...b,
            x: Math.max(0, Math.min(imgWidth - b.width, draggingBubble.initialX + deltaX)),
            y: Math.max(0, Math.min(imgHeight - b.height, draggingBubble.initialY + deltaY)),
          };
        } else {
          return {
            ...b,
            width: Math.max(20, draggingBubble.initialW + deltaX),
            height: Math.max(20, draggingBubble.initialH + deltaY),
          };
        }
      });
      latestDragBubblesRef.current = updated;
      onPreviewBubbles(updated);
    }
  };

  const handleMouseUp = () => {
    if (isPanning) {
      setIsPanning(false);
      return;
    }

    if (draggingBubble) {
      finishBubbleDrag();
    }
  };

  const startBubbleDrag = (e: React.MouseEvent, bubble: BubbleInfo, type: "move" | "resize") => {
    // Left button only; let right/middle clicks fall through (pan/context).
    if (e.button !== 0) return;
    e.stopPropagation();
    onSelectBubble(bubble.id);
    latestDragBubblesRef.current = null;
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
  };

  // Translate button: shows "Translating..." during processing, "Translate" otherwise.
  const translateButton = (
    <button
      className={isProcessing ? "primary processing" : "primary"}
      onClick={onTranslate}
      disabled={isProcessing}
      data-tooltip={isProcessing ? "Translating..." : (isMultiPageSelection ? `Translate ${selectedPageCount} pages` : "Translate current page")}
      data-tooltip-pos="top"
      aria-label="Translate"
    >
      <span className="translate-btn-icon">
        <Sparkles size={14} />
      </span>
      <span className="translate-btn-label">{isProcessing ? "Translating..." : "Translate"}</span>
    </button>
  );

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
        <div className="canvas-multi-select-empty">
          <Layers size={48} className="multi-select-icon" />
          <div className="multi-select-count">{selectedPageCount} pages selected</div>
        </div>
      ) : (
        <div
          className="canvas-viewport"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
            transformOrigin: "0 0",
            opacity: isImageLoading ? 0 : 1,
            transition: isImageLoading ? "none" : "opacity 0.15s ease-in-out"
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
                onLoad={handleImageLoad}
                onError={handleImageError}
                draggable={false}
                style={{
                  width: imageDimensions.w ? `${imageDimensions.w}px` : undefined,
                  height: imageDimensions.h ? `${imageDimensions.h}px` : undefined,
                }}
              />

              {/* Render Bubble Bounding Boxes & Text */}
              {!isWaitingForImageReload && (
                <svg
                  className="canvas-svg-overlay"
                  width={imageDimensions.w || "100%"}
                  height={imageDimensions.h || "100%"}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    pointerEvents: "none",
                    overflow: "visible"
                  }}
                >
                  {bubbles.map((b) => {
                  const isSelected = b.id === selectedBubbleId;
                  const statusColor = b.translated ? "var(--system-green)" : "var(--system-orange)";
                  return (
                    <g key={b.id}>
                      <rect
                        x={b.x}
                        y={b.y}
                        width={b.width}
                        height={b.height}
                        fill="rgba(0, 122, 255, 0.02)"
                        stroke={isSelected ? "var(--system-blue)" : statusColor}
                        strokeWidth={isSelected ? 3 / scale : 1.8 / scale}
                        style={{ pointerEvents: "auto", cursor: "move" }}
                        onMouseDown={(e) => startBubbleDrag(e, b, "move")}
                      />

                      {isSelected && (
                        <circle
                          cx={b.x + b.width}
                          cy={b.y + b.height}
                          r={6 / scale}
                          fill="var(--system-blue)"
                          stroke="white"
                          strokeWidth={1 / scale}
                          style={{ pointerEvents: "auto", cursor: "se-resize" }}
                          onMouseDown={(e) => startBubbleDrag(e, b, "resize")}
                        />
                      )}
                    </g>
                  );
                })}
                </svg>
              )}

              {!isWaitingForImageReload && (
              <div className="canvas-text-overlay" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
                {bubbles.map((b) => {
                  const showText = b.translated;
                  if (!showText) return null;
                  const isSelected = b.id === selectedBubbleId;

                  return (
                    <div
                      key={b.id}
                      className={`bubble-text-box ${isSelected ? "selected" : ""}`}
                      style={{
                        position: "absolute",
                        left: `${b.x}px`,
                        top: `${b.y}px`,
                        width: `${b.width}px`,
                        height: `${b.height}px`,
                        overflow: "hidden"
                      }}
                    >
                      {b.lines && b.lines.map((line, lIdx) => {
                        const lx = line.x - b.x;
                        const ly = line.y - b.y;
                        return (
                          <div
                            key={lIdx}
                            style={{
                              position: "absolute",
                              left: `${lx}px`,
                              top: `${ly}px`,
                              width: `${line.width}px`,
                              height: `${line.height}px`,
                              fontFamily: b.font_family || "var(--font-family)",
                              fontSize: `${b.font_size === 0 ? b.computed_font_size : b.font_size}px`,
                              fontWeight: b.bold ? "bold" : "normal",
                              fontStyle: b.italic ? "italic" : "normal",
                              color: b.color || "#000000",
                              textAlign: b.alignment as any,
                              lineHeight: `${line.height}px`,
                              whiteSpace: "nowrap",
                              textShadow: "0 0 3px #fff, 0 0 3px #fff, 0 0 2px #fff"
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
              )}


            </div>
          )}
        </div>
      )}

      {/* Floating control bar */}
      {displayImageUrl && (
        <div className="canvas-floating-controls">
          <div className="actions-capsule">
            {translateButton}
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
