import { useCallback, useEffect, useRef, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import * as api from "../services/api";
import type { PageInfo } from "../types";
import type { RunTask, WaitForJob } from "./useProcessingTask";

interface UseAutoTypesetDeps {
  pages: PageInfo[];
  selectedPageIds: number[];
  currentIndexRef: MutableRefObject<number>;
  runTask: RunTask;
  waitForJob: WaitForJob;
  syncBubblesToBackend: () => Promise<void>;
  setIsWaitingForImageReload: Dispatch<SetStateAction<boolean>>;
  bumpPageVersion: (idx: number) => void;
  loadPagesFromServer: (selectIndex?: number, options?: { skipPageActivation?: boolean }) => Promise<void>;
  fetchBubblesForPage: (pageIdx: number) => Promise<void>;
  setSelectedPageIds: Dispatch<SetStateAction<number[]>>;
  selectPage: (idx: number, options?: { deferActivation?: number }) => void;
  t?: (key: string) => string;
}

export function sortAutoTypesetPageIds(pageIds: number[]) {
  return [...pageIds].sort((a, b) => a - b);
}

export function resolveAutoTypesetDisplayIndex(sortedPageIds: number[], activeIdx: number) {
  if (sortedPageIds.length === 0) return null;
  return sortedPageIds.includes(activeIdx) ? activeIdx : sortedPageIds[0];
}

export function useAutoTypeset({
  pages,
  selectedPageIds,
  currentIndexRef,
  runTask,
  waitForJob,
  syncBubblesToBackend,
  setIsWaitingForImageReload,
  bumpPageVersion,
  loadPagesFromServer,
  fetchBubblesForPage,
  setSelectedPageIds,
  selectPage,
  t = (key) => key,
}: UseAutoTypesetDeps) {
  const selectedPageIdsRef = useRef<number[]>([]);

  useEffect(() => {
    selectedPageIdsRef.current = selectedPageIds;
  }, [selectedPageIds]);

  const handleTranslateCurrentPage = useCallback(async () => {
    const idx = currentIndexRef.current;
    if (idx < 0) return;
    const pageId = pages[idx]?.page_id;
    if (!pageId) return;
    await runTask(
      t("task.translatingPage"),
      async () => {
        const job = await api.translateAll(pageId);
        await waitForJob(job, t("task.translatingPage"));
        setIsWaitingForImageReload(true);
        bumpPageVersion(idx);
        await loadPagesFromServer(idx, { skipPageActivation: true });
        await fetchBubblesForPage(idx);
      },
      { errorTitle: t("task.translationFailed"), keepBusyOnSuccess: true }
    );
  }, [
    pages,
    currentIndexRef,
    runTask,
    waitForJob,
    setIsWaitingForImageReload,
    bumpPageVersion,
    loadPagesFromServer,
    fetchBubblesForPage,
    t,
  ]);

  const handleTranslatePages = useCallback(async (pageIds: number[]) => {
    const sorted = sortAutoTypesetPageIds(pageIds);
    const total = sorted.length;
    if (total === 0) return;
    const activeIdx = currentIndexRef.current;
    const displayIdx = resolveAutoTypesetDisplayIndex(sorted, activeIdx);
    if (displayIdx == null) return;

    await runTask(
      t("task.translatingPages").replace("{count}", String(total)),
      async () => {
        await syncBubblesToBackend();

        const job = await api.translateBatch(sorted);
        await waitForJob(job, t("task.translatingPages").replace("{count}", String(total)), {
          ignoreBackendMessage: true,
        });

        setIsWaitingForImageReload(true);
        for (const idx of sorted) bumpPageVersion(idx);

        setSelectedPageIds([displayIdx]);
        selectPage(displayIdx);
        await loadPagesFromServer(displayIdx, { skipPageActivation: true });
        await fetchBubblesForPage(displayIdx);
      },
      { errorTitle: t("task.multiPageTranslationFailed"), keepBusyOnSuccess: true }
    );
  }, [
    runTask,
    syncBubblesToBackend,
    waitForJob,
    currentIndexRef,
    setIsWaitingForImageReload,
    bumpPageVersion,
    loadPagesFromServer,
    fetchBubblesForPage,
    setSelectedPageIds,
    selectPage,
    t,
  ]);

  const handleTranslate = useCallback(async () => {
    const pageIds = [...selectedPageIdsRef.current];

    if (pageIds.length > 1) {
      return handleTranslatePages(pageIds);
    }

    return handleTranslateCurrentPage();
  }, [handleTranslatePages, handleTranslateCurrentPage]);

  return {
    handleTranslateCurrentPage,
    handleTranslatePages,
    handleTranslate,
  };
}
