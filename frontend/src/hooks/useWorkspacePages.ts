import { useCallback, useEffect, useRef } from "react";
import type { PageInfo } from "../types";
import { useBubbles } from "./useBubbles";
import { usePageImageRequests } from "./usePageImageRequests";
import { usePageSelection } from "./usePageSelection";
import { usePages } from "./usePages";
import type { RunTask, ShowError, WaitForJob } from "./useProcessingTask";

interface UseWorkspacePagesDeps {
  runTask: RunTask;
  waitForJob: WaitForJob;
  showError: ShowError;
  showConfirm: (
    title: string,
    message: string,
    onConfirm: () => void,
    confirmText?: string,
    cancelText?: string,
    destructive?: boolean
  ) => void;
  markDirty: () => void;
  markPagesDeleted: (remainingPageCount: number) => void;
  /** Passed through to useBubbles for the delete-undo toast. */
  onBubbleDeleted?: (undo: () => void) => void;
  t?: (key: string) => string;
}

export function useWorkspacePages({
  runTask,
  waitForJob,
  showError,
  showConfirm,
  markDirty,
  markPagesDeleted,
  onBubbleDeleted,
  t = (key) => key,
}: UseWorkspacePagesDeps) {
  const selectionRef = useRef<number[]>([]);
  const getSelectedIndices = useCallback(() => selectionRef.current, []);

  const currentIndexRef = useRef<number>(-1);
  const pagesRef = useRef<PageInfo[]>([]);
  const onTranslationChangedRef = useRef<(() => void) | undefined>(undefined);

  const bubblesApi = useBubbles({
    currentIndexRef,
    pagesRef,
    runTask,
    waitForJob,
    showError,
    markDirty,
    onPageTranslationChanged: () => onTranslationChangedRef.current?.(),
    onBubbleDeleted,
    t,
  });

  const pagesApi = usePages({
    currentIndexRef,
    runTask,
    showError,
    showConfirm,
    onPageActivated: bubblesApi.handlePageActivated,
    onPagesCleared: bubblesApi.clearBubbles,
    markDirty,
    markPagesDeleted,
    t,
  });

  const { pages, currentIndex, pageVersions, loadPagesFromServer } = pagesApi;

  useEffect(() => {
    pagesRef.current = pages;
  }, [pages]);

  useEffect(() => {
    onTranslationChangedRef.current = () => loadPagesFromServer();
  }, [loadPagesFromServer]);

  const { selectedBubbleId, setSelectedBubbleId } = bubblesApi;
  const clearBubbleSelection = useCallback(() => setSelectedBubbleId(null), [setSelectedBubbleId]);

  const selectionApi = usePageSelection({
    pages,
    currentIndex,
    selectionRef,
    selectPage: pagesApi.handleSelectPage,
    clearBubbleSelection,
  });
  const { setSelectedPageIds } = selectionApi;
  const { clearBubbles } = bubblesApi;
  const { clearPagesForBackendRestart } = pagesApi;

  const resetForBackendRestart = useCallback(() => {
    selectionRef.current = [];
    currentIndexRef.current = -1;
    pagesRef.current = [];
    setSelectedPageIds([]);
    clearBubbles();
    clearPagesForBackendRestart();
  }, [clearBubbles, clearPagesForBackendRestart, setSelectedPageIds]);

  const { buildPageImageUrl } = usePageImageRequests({
    pages,
    currentIndex,
    pageVersions,
  });

  const activePage = pages[currentIndex];
  const activeBubble = bubblesApi.bubbles.find((b) => b.id === selectedBubbleId) || null;
  const isMultiPageSelection = selectionApi.selectedPageIds.length > 1;

  return {
    activeBubble,
    activePage,
    bubblesApi,
    buildPageImageUrl,
    currentIndex,
    currentIndexRef,
    getSelectedIndices,
    isMultiPageSelection,
    loadPagesFromServer,
    pages,
    pagesApi,
    selectionApi,
    resetForBackendRestart,
  };
}
