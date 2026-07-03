import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type RefObject,
  type SetStateAction,
} from "react";

interface UseCanvasImageLoaderOptions {
  containerRef: RefObject<HTMLDivElement | null>;
  imageRef: RefObject<HTMLImageElement | null>;
  imageUrl: string;
  fullResImageUrl?: string;
  imageWidth?: number;
  imageHeight?: number;
  pageIndex: number;
  scale: number;
  setScale: Dispatch<SetStateAction<number>>;
  setPan: Dispatch<SetStateAction<{ x: number; y: number }>>;
  hasUserAdjustedRef: MutableRefObject<boolean>;
  onImageLoaded?: () => void;
}

export function useCanvasImageLoader({
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
}: UseCanvasImageLoaderOptions) {
  const [isImageLoading, setIsImageLoading] = useState<boolean>(true);
  const [displayImageUrl, setDisplayImageUrl] = useState<string>(imageUrl);
  const [isUsingFullRes, setIsUsingFullRes] = useState<boolean>(false);
  const [imageDimensions, setImageDimensions] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const fullResRequestRef = useRef<number>(0);
  const fullResPreloadUrlRef = useRef<string>("");
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
  }, [hasUserAdjustedRef, pageIndex, setScale]);

  useLayoutEffect(() => {
    fullResRequestRef.current += 1;
    fullResPreloadUrlRef.current = "";
    setDisplayImageUrl(imageUrl);
    setIsUsingFullRes(false);
  }, [imageUrl]);

  const handleImageLoad = useCallback(() => {
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
  }, [containerRef, imageHeight, imageRef, imageWidth, isImageLoading, onImageLoaded, setPan, setScale]);

  const handleImageError = useCallback(() => {
    if (onImageLoaded) {
      onImageLoaded();
    }
  }, [onImageLoaded]);

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

  return {
    displayImageUrl,
    imageDimensions,
    isImageLoading,
    setImageDimensions,
    handleImageLoad,
    handleImageError,
  };
}
