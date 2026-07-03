import { useEffect } from "react";

interface UseAppChromeDeps {
  openSettings: () => void;
}

export function useAppChrome({ openSettings }: UseAppChromeDeps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const activeTag = document.activeElement?.tagName.toLowerCase();
      if (activeTag === "input" || activeTag === "textarea" || activeTag === "select") {
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key === ",") {
        event.preventDefault();
        openSettings();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [openSettings]);

  useEffect(() => {
    const handleGlobalContextMenu = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target) return;
      const isAllowed =
        target.closest(".canvas-container") ||
        target.closest(".page-item") ||
        target.closest(".sidebar-context-menu") ||
        target.tagName.toLowerCase() === "input" ||
        target.tagName.toLowerCase() === "textarea";
      if (!isAllowed) event.preventDefault();
    };
    window.addEventListener("contextmenu", handleGlobalContextMenu);
    return () => window.removeEventListener("contextmenu", handleGlobalContextMenu);
  }, []);
}
