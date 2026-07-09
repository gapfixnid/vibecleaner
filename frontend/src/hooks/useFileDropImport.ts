import { useEffect, useRef, useState } from "react";

const IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "webp", "bmp"]);

function splitImagePaths(paths: string[]): { images: string[]; skipped: number } {
  const images = paths.filter((path) => {
    const dot = path.lastIndexOf(".");
    if (dot < 0) return false;
    return IMAGE_EXTENSIONS.has(path.slice(dot + 1).toLowerCase());
  });
  return { images, skipped: paths.length - images.length };
}

interface UseFileDropImportDeps {
  /** Disable while a blocking modal (setup/backend error) is up. */
  enabled: boolean;
  /** Called with the dropped image paths and the count of skipped non-images. */
  onDropImages: (imagePaths: string[], skippedCount: number) => void;
}

/**
 * OS-level file drag-and-drop import via the Tauri webview drag-drop events.
 * No-ops silently outside Tauri (plain-browser vite dev).
 */
export function useFileDropImport({ enabled, onDropImages }: UseFileDropImportDeps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const depsRef = useRef({ enabled, onDropImages });
  depsRef.current = { enabled, onDropImages };

  useEffect(() => {
    let unlisten: (() => void) | null = null;
    let disposed = false;

    (async () => {
      try {
        const { getCurrentWebview } = await import("@tauri-apps/api/webview");
        const webview = getCurrentWebview();
        const stop = await webview.onDragDropEvent((event) => {
          const { enabled: isEnabled, onDropImages: handleDrop } = depsRef.current;
          if (!isEnabled) {
            setIsDragOver(false);
            return;
          }
          if (event.payload.type === "enter" || event.payload.type === "over") {
            setIsDragOver(true);
          } else if (event.payload.type === "leave") {
            setIsDragOver(false);
          } else if (event.payload.type === "drop") {
            setIsDragOver(false);
            const { images, skipped } = splitImagePaths(event.payload.paths ?? []);
            if (images.length > 0 || skipped > 0) {
              handleDrop(images, skipped);
            }
          }
        });
        if (disposed) {
          stop();
        } else {
          unlisten = stop;
        }
      } catch {
        // Not running inside Tauri — drag-and-drop import unavailable.
      }
    })();

    return () => {
      disposed = true;
      unlisten?.();
    };
  }, []);

  return { isDragOver } as const;
}
