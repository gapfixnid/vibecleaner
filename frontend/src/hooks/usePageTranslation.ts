import { useCallback, useEffect, useRef, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import * as api from "../services/api";
import type { PageInfo } from "../types";
import type { RunTask, ShowError, WaitForJob } from "./useProcessingTask";

interface BatchTranslationResult {
  successful_page_indices?: number[];
  failed_pages?: Array<{ page_id: string; page_idx: number | null; error: string }>;
}

interface UsePageTranslationDeps {
  pages: PageInfo[];
  selectedPageIds: number[];
  currentIndexRef: MutableRefObject<number>;
  runTask: RunTask;
  waitForJob: WaitForJob;
  showError: ShowError;
  syncBubblesToBackend: () => Promise<void>;
  setIsWaitingForImageReload: Dispatch<SetStateAction<boolean>>;
  bumpPageVersion: (idx: number) => void;
  loadPagesFromServer: (selectIndex?: number, options?: { skipPageActivation?: boolean }) => Promise<void>;
  fetchBubblesForPage: (pageIdx: number) => Promise<void>;
  setSelectedPageIds: Dispatch<SetStateAction<number[]>>;
  selectPage: (idx: number, options?: { deferActivation?: number }) => void;
  t?: (key: string) => string;
}

export function sortPageTranslationIds(pageIds: number[]) {
  return [...pageIds].sort((a, b) => a - b);
}

export function resolvePageTranslationDisplayIndex(sortedPageIds: number[], activeIdx: number) {
  if (sortedPageIds.length === 0) return null;
  return sortedPageIds.includes(activeIdx) ? activeIdx : sortedPageIds[0];
}

export function usePageTranslation({
  pages,
  selectedPageIds,
  currentIndexRef,
  runTask,
  waitForJob,
  showError,
  syncBubblesToBackend,
  setIsWaitingForImageReload,
  bumpPageVersion,
  loadPagesFromServer,
  fetchBubblesForPage,
  setSelectedPageIds,
  selectPage,
  t = (key) => key,
}: UsePageTranslationDeps) {
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
    const sorted = sortPageTranslationIds(pageIds);
    const total = sorted.length;
    if (total === 0) return;
    const activeIdx = currentIndexRef.current;
    const displayIdx = resolvePageTranslationDisplayIndex(sorted, activeIdx);
    if (displayIdx == null) return;

    await runTask(
      t("task.translatingPages").replace("{count}", String(total)),
      async () => {
        await syncBubblesToBackend();

        const job = await api.translateBatch(sorted);
        const result = await waitForJob(job, t("task.translatingPages").replace("{count}", String(total)), {
          ignoreBackendMessage: true,
        }) as BatchTranslationResult | undefined;
        const successfulPageIndices = result?.successful_page_indices ?? sorted;
        const failedPages = result?.failed_pages ?? [];
        const reloadIdx = successfulPageIndices.includes(displayIdx)
          ? displayIdx
          : successfulPageIndices[0] ?? displayIdx;

        setIsWaitingForImageReload(true);
        for (const idx of successfulPageIndices) bumpPageVersion(idx);

        setSelectedPageIds([reloadIdx]);
        selectPage(reloadIdx);
        await loadPagesFromServer(reloadIdx, { skipPageActivation: true });
        await fetchBubblesForPage(reloadIdx);

        if (failedPages.length > 0) {
          const details = failedPages
            .map((page) => {
              const pageLabel = page.page_idx == null ? page.page_id : String(page.page_idx + 1);
              return t("task.failedPage").replace("{page}", pageLabel).replace("{error}", page.error);
            })
            .join("\n");
          showError(t("task.multiPageTranslationPartial"), details);
        }
      },
      { errorTitle: t("task.multiPageTranslationFailed"), keepBusyOnSuccess: true }
    );
  }, [
    runTask,
    syncBubblesToBackend,
    waitForJob,
    showError,
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
