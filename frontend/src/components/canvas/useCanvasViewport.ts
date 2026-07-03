import {
  useCallback,
  useEffect,
  useState,
  type Dispatch,
  type MutableRefObject,
  type RefObject,
  type SetStateAction,
} from "react";
import type React from "react";

interface UseCanvasViewportOptions {
  containerRef: RefObject<HTMLDivElement | null>;
  imageRef: RefObject<HTMLImageElement | null>;
  imageWidth?: number;
  imageHeight?: number;
  imageDimensions: { w: number; h: number };
  setImageDimensions: Dispatch<SetStateAction<{ w: number; h: number }>>;
  isImageLoading: boolean;
  scale: number;
  setScale: Dispatch<SetStateAction<number>>;
  pan: { x: number; y: number };
  setPan: Dispatch<SetStateAction<{ x: number; y: number }>>;
  hasUserAdjustedRef: MutableRefObject<boolean>;
}

export function useCanvasViewport({
  containerRef,
  imageRef,
  imageWidth,
  imageHeight,
  setImageDimensions,
  isImageLoading,
  scale,
  setScale,
  pan,
  setPan,
  hasUserAdjustedRef,
}: UseCanvasViewportOptions) {
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isSpacePressed, setIsSpacePressed] = useState<boolean>(false);

  // Recalculate scale/pan on resize.
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
  }, [containerRef, hasUserAdjustedRef, imageHeight, imageRef, imageWidth, setImageDimensions, setPan, setScale]);

  // Self-correction hook.
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
  }, [
    containerRef,
    hasUserAdjustedRef,
    imageHeight,
    imageRef,
    imageWidth,
    isImageLoading,
    scale,
    setImageDimensions,
    setPan,
    setScale,
  ]);

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
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
    },
    [containerRef, hasUserAdjustedRef, isSpacePressed, pan.x, pan.y, scale, setPan, setScale],
  );

  const startCanvasPan = useCallback(
    (e: React.MouseEvent) => {
      if (isSpacePressed || e.button === 1 || e.button === 2) {
        e.preventDefault();
        hasUserAdjustedRef.current = true;
        setIsPanning(true);
        setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
        return true;
      }
      return false;
    },
    [hasUserAdjustedRef, isSpacePressed, pan.x, pan.y],
  );

  const updateCanvasPan = useCallback(
    (e: React.MouseEvent) => {
      if (!isPanning) return false;
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
      return true;
    },
    [isPanning, panStart.x, panStart.y, setPan],
  );

  const finishCanvasPan = useCallback(() => {
    if (!isPanning) return false;
    setIsPanning(false);
    return true;
  }, [isPanning]);

  return {
    handleWheel,
    isPanning,
    isSpacePressed,
    setIsSpacePressed,
    startCanvasPan,
    updateCanvasPan,
    finishCanvasPan,
  };
}
