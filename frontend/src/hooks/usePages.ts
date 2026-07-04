import { useState, useCallback, useEffect, type MutableRefObject } from "react";
import * as api from "../services/api";
import type { PageInfo } from "../types";
import type { RunTask, ShowError } from "./useProcessingTask";

interface UsePagesDeps {
  currentIndexRef: MutableRefObject<number>;
  runTask: RunTask;
  showError: ShowError;
  showConfirm: (
    title: string,
    message: string,
    onConfirm: () => void,
    confirmText?: string,
    cancelText?: string,
    destructive?: boolean
  ) => void;
  /** Invoked when a page becomes active (load its bubbles). */
  onPageActivated: (idx: number) => void;
  /** Invoked when there is no active page. */
  onPagesCleared: () => void;
  /** Mark the project dirty (duplicate / delete / reorder mutate pages). */
  markDirty: () => void;
  t?: (key: string) => string;
}

/** Owns the page list, current index, and per-page cache-busting versions. */
export function usePages({
  currentIndexRef,
  runTask,
  showError,
  showConfirm,
  onPageActivated,
  onPagesCleared,
  markDirty,
  t = (key) => key,
}: UsePagesDeps) {
  const [pages, setPages] = useState<PageInfo[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(-1);
  const [pageVersions, setPageVersions] = useState<Record<number, number>>({});

  useEffect(() => {
    currentIndexRef.current = currentIndex;
  }, [currentIndex, currentIndexRef]);

  const bumpPageVersion = useCallback((idx: number) => {
    setPageVersions((prev) => ({ ...prev, [idx]: (prev[idx] || 0) + 1 }));
  }, []);

  const resetPageVersions = useCallback(() => {
    setPageVersions({});
  }, []);

  const loadPagesFromServer = useCallback(
    async (selectIndex?: number, options?: { skipPageActivation?: boolean }) => {
      try {
        const data = await api.getPages();
        setPages(data.pages);
        const newIdx = selectIndex !== undefined ? selectIndex : data.current_index;
        currentIndexRef.current = newIdx;
        setCurrentIndex(newIdx);
        if (options?.skipPageActivation) {
          // Metadata-only change (e.g. rename) — skip bubble fetch
          return;
        }
        if (newIdx >= 0) {
          onPageActivated(newIdx);
        } else {
          onPagesCleared();
        }
      } catch (e) {
        console.error("Failed to fetch pages", e);
        showError(t("pages.loadFailedTitle"), t("pages.loadFailedMessage"));
      }
    },
    [currentIndexRef, onPageActivated, onPagesCleared, showError, t]
  );

  const handleSelectPage = useCallback(
    (idx: number, options?: { deferActivation?: number }) => {
      const previousIndex = currentIndexRef.current;
      if (idx === previousIndex) return;
      // Zero-latency switch: update UI immediately, sync backend in background.
      currentIndexRef.current = idx;
      setCurrentIndex(idx);

      if (options?.deferActivation != null) {
        // Defer bubble fetch to let the inpainted image load first.
        // The defer time (ms) should exceed the typical image render time.
        window.setTimeout(() => onPageActivated(idx), options.deferActivation);
      } else {
        onPageActivated(idx);
      }

      const pageId = pages[idx]?.page_id;
      api.selectPage(idx, pageId).catch((err) => {
        console.error("Failed to sync selected page on backend", err);
        if (currentIndexRef.current !== idx) return;

        currentIndexRef.current = previousIndex;
        setCurrentIndex(previousIndex);
        if (previousIndex >= 0) {
          window.setTimeout(() => onPageActivated(previousIndex), options?.deferActivation ?? 0);
        } else {
          onPagesCleared();
        }
        showError(t("pages.switchFailedTitle"), t("pages.switchFailedMessage"));
      });
    },
    [currentIndexRef, onPageActivated, onPagesCleared, pages, showError, t]
  );

  const handleDuplicatePage = useCallback(
    async (idx: number) => {
      await runTask(
        t("pages.duplicatingPage"),
        async () => {
          const pageId = pages[idx]?.page_id;
          const data = await api.duplicatePage(idx, pageId);
          await loadPagesFromServer(data.current_index);
          markDirty();
        },
        { errorTitle: t("pages.failedToDuplicatePage") }
      );
    },
    [runTask, loadPagesFromServer, markDirty, pages, t]
  );

  const handleDuplicatePages = useCallback(
    async (indices: number[]) => {
      if (indices.length === 0) return;
      const count = indices.length;
      await runTask(
        count > 1 ? t("pages.duplicatingPages").replace("{count}", String(count)) : t("pages.duplicatingPage"),
        async () => {
          const pageIds = indices.map((i) => pages[i]?.page_id).filter(Boolean) as string[];
          if (count > 1) {
            const data = await api.duplicatePagesBatch(indices, pageIds);
            await loadPagesFromServer(data.current_index);
          } else {
            const pageId = pages[indices[0]]?.page_id;
            const data = await api.duplicatePage(indices[0], pageId);
            await loadPagesFromServer(data.current_index);
          }
          markDirty();
        },
        { errorTitle: t("pages.failedToDuplicatePage") }
      );
    },
    [runTask, loadPagesFromServer, markDirty, pages, t]
  );

  const handleDeletePages = useCallback(
    (indices: number[]) => {
      const count = indices.length;
      showConfirm(
        count > 1 ? t("pages.deletePagesTitle") : t("pages.deletePageTitle"),
        count > 1
          ? t("pages.deletePagesMessage").replace("{count}", String(count))
          : t("pages.deletePageMessage"),
        async () => {
          await runTask(
            count > 1 ? t("pages.deletingPages").replace("{count}", String(count)) : t("pages.deletingPage"),
            async () => {
              const pageIds = indices.map((i) => pages[i]?.page_id).filter(Boolean) as string[];
              if (count > 1) {
                const data = await api.deletePagesBatch(indices, pageIds);
                await loadPagesFromServer(data.current_index);
              } else {
                const pageId = pages[indices[0]]?.page_id;
                const data = await api.deletePage(indices[0], pageId);
                await loadPagesFromServer(data.current_index);
              }
              markDirty();
            },
            { errorTitle: t("pages.failedToDeletePage") }
          );
        },
        t("sidebar.delete"),
        t("dialog.cancel"),
        true
      );
    },
    [showConfirm, runTask, loadPagesFromServer, markDirty, pages, t]
  );

  const handleReorderPages = useCallback(
    async (fromIdx: number, toIdx: number) => {
      await runTask(
        t("pages.reorderingPages"),
        async () => {
          const data = await api.reorderPages(fromIdx, toIdx);
          await loadPagesFromServer(data.current_index);
          markDirty();
        },
        { errorTitle: t("pages.failedToReorderPages") }
      );
    },
    [runTask, loadPagesFromServer, markDirty, t]
  );

  return {
    pages,
    setPages,
    currentIndex,
    setCurrentIndex,
    pageVersions,
    bumpPageVersion,
    resetPageVersions,
    loadPagesFromServer,
    handleSelectPage,
    handleDuplicatePage,
    handleDuplicatePages,
    handleDeletePages,
    handleReorderPages,
  };
}
