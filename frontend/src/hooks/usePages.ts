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
        showError("페이지 로드 실패", "페이지 목록을 불러오지 못했습니다.");
      }
    },
    [currentIndexRef, onPageActivated, onPagesCleared, showError]
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
        showError("페이지 전환 실패", "선택한 페이지로 전환하지 못했습니다.");
      });
    },
    [currentIndexRef, onPageActivated, onPagesCleared, pages, showError]
  );

  const handleDuplicatePage = useCallback(
    async (idx: number) => {
      await runTask(
        "Duplicating page...",
        async () => {
          const pageId = pages[idx]?.page_id;
          const data = await api.duplicatePage(idx, pageId);
          await loadPagesFromServer(data.current_index);
          markDirty();
        },
        { errorTitle: "Failed to Duplicate Page" }
      );
    },
    [runTask, loadPagesFromServer, markDirty, pages]
  );

  const handleDuplicatePages = useCallback(
    async (indices: number[]) => {
      if (indices.length === 0) return;
      const count = indices.length;
      await runTask(
        count > 1 ? `Duplicating ${count} pages...` : "Duplicating page...",
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
        { errorTitle: "Failed to Duplicate Page" }
      );
    },
    [runTask, loadPagesFromServer, markDirty, pages]
  );

  const handleDeletePages = useCallback(
    (indices: number[]) => {
      const count = indices.length;
      showConfirm(
        "Delete Page" + (count > 1 ? "s" : ""),
        count > 1
          ? `Are you sure you want to delete ${count} pages? This action cannot be undone.`
          : "Are you sure you want to delete this page? This action cannot be undone.",
        async () => {
          await runTask(
            count > 1 ? `Deleting ${count} pages...` : "Deleting page...",
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
            { errorTitle: "Failed to Delete Page" }
          );
        },
        "Delete",
        "Cancel",
        true
      );
    },
    [showConfirm, runTask, loadPagesFromServer, markDirty, pages]
  );

  const handleReorderPages = useCallback(
    async (fromIdx: number, toIdx: number) => {
      await runTask(
        "Reordering pages...",
        async () => {
          const data = await api.reorderPages(fromIdx, toIdx);
          await loadPagesFromServer(data.current_index);
          markDirty();
        },
        { errorTitle: "Failed to Reorder Pages" }
      );
    },
    [runTask, loadPagesFromServer, markDirty]
  );

  return {
    pages,
    setPages,
    currentIndex,
    setCurrentIndex,
    pageVersions,
    bumpPageVersion,
    loadPagesFromServer,
    handleSelectPage,
    handleDuplicatePage,
    handleDuplicatePages,
    handleDeletePages,
    handleReorderPages,
  };
}
