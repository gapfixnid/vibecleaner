import { useEffect } from "react";
import { isTextInputFocused } from "../lib/keyboard";

interface UseAppChromeDeps {
  openSettings: () => void;
  /** Ctrl+S */
  onSaveProject?: () => void;
  /** Ctrl+O */
  onOpenProject?: () => void;
  /** Ctrl+Shift+N (plain Ctrl+N is too easy to hit with unsaved work). */
  onNewProject?: () => void;
  /** Ctrl+T */
  onTranslate?: () => void;
  /** PageUp/PageDown page navigation: delta is -1 or +1. */
  onPageStep?: (delta: number) => void;
}

export function useAppChrome({
  openSettings,
  onSaveProject,
  onOpenProject,
  onNewProject,
  onTranslate,
  onPageStep,
}: UseAppChromeDeps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isTextInputFocused()) {
        return;
      }
      const mod = event.ctrlKey || event.metaKey;
      if (mod && event.key === ",") {
        event.preventDefault();
        openSettings();
        return;
      }
      if (mod && !event.shiftKey && event.key.toLowerCase() === "s") {
        event.preventDefault();
        onSaveProject?.();
        return;
      }
      if (mod && !event.shiftKey && event.key.toLowerCase() === "o") {
        event.preventDefault();
        onOpenProject?.();
        return;
      }
      if (mod && event.shiftKey && event.key.toLowerCase() === "n") {
        event.preventDefault();
        onNewProject?.();
        return;
      }
      if (mod && !event.shiftKey && event.key.toLowerCase() === "t") {
        event.preventDefault();
        onTranslate?.();
        return;
      }
      if (!mod && event.key === "PageUp") {
        event.preventDefault();
        onPageStep?.(-1);
        return;
      }
      if (!mod && event.key === "PageDown") {
        event.preventDefault();
        onPageStep?.(1);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [openSettings, onSaveProject, onOpenProject, onNewProject, onTranslate, onPageStep]);

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
