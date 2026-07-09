import { useState, useRef, useCallback, useEffect, type MutableRefObject } from "react";
import * as api from "../services/api";
import type { BubbleInfo, BubbleUpdate, PageInfo } from "../types";
import type { RunTask, WaitForJob, ShowError } from "./useProcessingTask";

interface UseBubblesDeps {
  /** Ref to the active page index, owned by usePages/App. */
  currentIndexRef: MutableRefObject<number>;
  /** Ref to the page list, owned by App. */
  pagesRef: MutableRefObject<PageInfo[]>;
  runTask: RunTask;
  waitForJob: WaitForJob;
  showError: ShowError;
  /** Mark the project dirty (called when bubbles are persisted/changed). */
  markDirty: () => void;
  /** Called when translated count may have changed so sidebar dots refresh. */
  onPageTranslationChanged?: () => void;
  /** Called after a bubble was deleted, with a callback that restores it (undo toast). */
  onBubbleDeleted?: (undo: () => void) => void;
  t?: (key: string) => string;
}

function toBubbleUpdate(b: BubbleInfo): BubbleUpdate {
  return {
    id: b.id,
    x: b.x,
    y: b.y,
    width: b.width,
    height: b.height,
    text: b.text,
    translated: b.translated,
    font_family: b.font_family,
    font_size: b.font_size,
    computed_font_size: b.computed_font_size,
    bold: b.bold,
    italic: b.italic,
    color: b.color,
    alignment: b.alignment,
  };
}

/** Return true if the translated field changed between old and new bubble. */
function translationStatusChanged(oldB: BubbleInfo | undefined, newB: BubbleInfo): boolean {
  const oldWasTranslated = !!(oldB?.translated || "").trim();
  const newIsTranslated = !!(newB.translated || "").trim();
  return oldWasTranslated !== newIsTranslated;
}

/** Owns bubble list state, selection, and all bubble-level operations. */
export function useBubbles({ currentIndexRef, pagesRef, runTask, waitForJob, showError, markDirty, onPageTranslationChanged, onBubbleDeleted, t = (key) => key }: UseBubblesDeps) {
  const [bubbles, setBubbles] = useState<BubbleInfo[]>([]);
  const [selectedBubbleId, setSelectedBubbleId] = useState<number | null>(null);
  const bubbleRequestSeq = useRef(0);
  const bubblesRef = useRef<BubbleInfo[]>([]);

  useEffect(() => {
    bubblesRef.current = bubbles;
  }, [bubbles]);

  const getPageId = useCallback((idx?: number) => {
    const pageIndex = idx !== undefined ? idx : currentIndexRef.current;
    if (pageIndex < 0 || pageIndex >= pagesRef.current.length) return null;
    return pagesRef.current[pageIndex].page_id;
  }, [currentIndexRef, pagesRef]);

  const fetchBubblesForPage = useCallback(
    async (pageIdx: number) => {
      const requestId = ++bubbleRequestSeq.current;
      const pageId = getPageId(pageIdx);
      if (!pageId) return;
      try {
        const data = await api.getBubbles(pageId);
        if (requestId === bubbleRequestSeq.current && pageIdx === currentIndexRef.current) {
          setBubbles(data.bubbles);
        }
      } catch (e) {
        console.error("Failed to fetch bubbles for page", pageIdx, e);
        // Don't show error for stale requests (e.g. page was deleted while fetch was in flight).
        // Verify the pageId still exists in the current page list.
        const currentPageId = getPageId(pageIdx);
        if (requestId === bubbleRequestSeq.current && pageIdx === currentIndexRef.current && currentPageId === pageId) {
          showError(t("bubbles.loadFailedTitle"), t("bubbles.loadFailedMessage"));
        }
      }
    },
    [currentIndexRef, getPageId, showError, t]
  );

  /** Called by usePages when a page becomes active: clear then load. */
  const handlePageActivated = useCallback(
    (idx: number) => {
      bubbleRequestSeq.current += 1;
      setSelectedBubbleId(null);
      setBubbles([]);
      window.setTimeout(() => {
        fetchBubblesForPage(idx);
      }, 0);
    },
    [fetchBubblesForPage]
  );

  const clearBubbles = useCallback(() => {
    bubbleRequestSeq.current += 1;
    setBubbles([]);
    setSelectedBubbleId(null);
  }, []);

  const syncBubblesToBackend = useCallback(
    async (bubblesList?: BubbleInfo[], opts?: { silent?: boolean }) => {
      const pageId = getPageId();
      if (!pageId) return;
      const source = bubblesList ?? bubblesRef.current;
      await api.updateBubbles(pageId, source.map(toBubbleUpdate));
      // `silent` skips dirty-marking for read-only flows (e.g. export, which
      // only persists pending edits to render — not a user-initiated change).
      if (!opts?.silent) markDirty();
    },
    [getPageId, markDirty]
  );

  const handlePreviewBubbles = useCallback((updatedList: BubbleInfo[]) => {
    setBubbles(updatedList);
  }, []);

  const handleUpdateBubble = useCallback(
    async (updated: BubbleInfo) => {
      const idx = currentIndexRef.current;
      const prev = bubblesRef.current;
      const prevBubble = prev.find((b) => b.id === updated.id);
      const updatedList = prev.map((b) => (b.id === updated.id ? updated : b));
      setBubbles(updatedList);
      try {
        await syncBubblesToBackend(updatedList);
      } catch (e) {
        console.error("Failed to update bubble", e);
        setBubbles(prev); // rollback optimistic change
        showError(t("bubbles.saveFailedTitle"), t("bubbles.saveFailedMessage"));
        return;
      }
      await fetchBubblesForPage(idx);
      // Notify parent so sidebar dots reflect updated translated_count
      if (translationStatusChanged(prevBubble, updated)) {
        onPageTranslationChanged?.();
      }
    },
    [currentIndexRef, syncBubblesToBackend, fetchBubblesForPage, showError, onPageTranslationChanged, t]
  );

  const handleUpdateBubbles = useCallback(
    async (updatedList: BubbleInfo[]) => {
      const idx = currentIndexRef.current;
      const prev = bubblesRef.current;
      setBubbles(updatedList);
      try {
        await syncBubblesToBackend(updatedList);
      } catch (e) {
        console.error("Failed to update bubbles", e);
        setBubbles(prev); // rollback optimistic change
        showError(t("bubbles.saveFailedTitle"), t("bubbles.saveFailedMessage"));
        return;
      }
      await fetchBubblesForPage(idx);
    },
    [currentIndexRef, syncBubblesToBackend, fetchBubblesForPage, showError, t]
  );

  const handleReOcrBubble = useCallback(
    async (bubbleId: number) => {
      const idx = currentIndexRef.current;
      const pageId = getPageId(idx);
      if (!pageId) return;
      await runTask(
        t("bubbles.reRunningOcr"),
        async () => {
          await syncBubblesToBackend();
          await api.reOcrBubble(pageId, bubbleId);
          await fetchBubblesForPage(idx);
        },
        { errorTitle: t("bubbles.ocrFailed") }
      );
    },
    [currentIndexRef, getPageId, runTask, syncBubblesToBackend, fetchBubblesForPage, t]
  );

  const handleReTranslateBubble = useCallback(
    async (bubbleId: number) => {
      const idx = currentIndexRef.current;
      const pageId = getPageId(idx);
      if (!pageId) return;
      await runTask(
        t("bubbles.translatingSpeechBubble"),
        async () => {
          await syncBubblesToBackend();
          const job = await api.translateBubble(pageId, bubbleId);
          await waitForJob(job, t("bubbles.translatingSpeechBubble"));
          await fetchBubblesForPage(idx);
        },
        { errorTitle: t("bubbles.translationFailed") }
      );
    },
    [currentIndexRef, getPageId, runTask, waitForJob, syncBubblesToBackend, fetchBubblesForPage, t]
  );

  const handleDeleteBubble = useCallback(
    async (bubbleId: number) => {
      const idx = currentIndexRef.current;
      const pageId = getPageId(idx);
      if (!pageId) return;
      const prev = bubblesRef.current;
      const prevSelected = bubbleId;
      const updated = prev.filter((b) => b.id !== bubbleId);
      setBubbles(updated);
      setSelectedBubbleId(null);
      try {
        await syncBubblesToBackend(updated);
      } catch (e) {
        console.error("Failed to delete bubble", e);
        setBubbles(prev); // rollback
        setSelectedBubbleId(prevSelected);
        showError(t("bubbles.deleteFailedTitle"), t("bubbles.deleteFailedMessage"));
        return;
      }
      await fetchBubblesForPage(idx);
      // Deleting a bubble changes translated_count
      onPageTranslationChanged?.();
      // Offer undo: restoring re-sends the pre-delete list (full-list sync).
      onBubbleDeleted?.(() => {
        void (async () => {
          try {
            await syncBubblesToBackend(prev);
            await fetchBubblesForPage(idx);
            onPageTranslationChanged?.();
          } catch (e) {
            console.error("Failed to restore deleted bubble", e);
            showError(t("bubbles.saveFailedTitle"), t("bubbles.saveFailedMessage"));
          }
        })();
      });
    },
    [currentIndexRef, getPageId, syncBubblesToBackend, fetchBubblesForPage, showError, onPageTranslationChanged, onBubbleDeleted, t]
  );

  return {
    bubbles,
    setBubbles,
    selectedBubbleId,
    setSelectedBubbleId,
    fetchBubblesForPage,
    handlePageActivated,
    clearBubbles,
    syncBubblesToBackend,
    handlePreviewBubbles,
    handleUpdateBubble,
    handleUpdateBubbles,
    handleReOcrBubble,
    handleReTranslateBubble,
    handleDeleteBubble,
  };
}
