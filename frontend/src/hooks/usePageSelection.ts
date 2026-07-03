import { useCallback, useEffect, useRef, useState, type MutableRefObject, type MouseEvent } from "react";
import type { PageInfo } from "../types";

interface UsePageSelectionDeps {
  pages: PageInfo[];
  currentIndex: number;
  selectionRef: MutableRefObject<number[]>;
  selectPage: (idx: number) => void;
  clearBubbleSelection: () => void;
}

export function usePageSelection({
  pages,
  currentIndex,
  selectionRef,
  selectPage,
  clearBubbleSelection,
}: UsePageSelectionDeps) {
  const [selectedPageIds, setSelectedPageIds] = useState<number[]>([]);
  const rangeAnchorRef = useRef<number | null>(null);

  useEffect(() => {
    selectionRef.current = selectedPageIds;
  }, [selectedPageIds, selectionRef]);

  useEffect(() => {
    rangeAnchorRef.current = currentIndex;
  }, [currentIndex]);

  useEffect(() => {
    if (selectedPageIds.length > 1) {
      clearBubbleSelection();
    }
  }, [selectedPageIds.length, clearBubbleSelection]);

  const handlePageSelection = useCallback(
    (event: MouseEvent, pageIdx: number) => {
      if (event.ctrlKey || event.metaKey) {
        const exists = selectedPageIds.includes(pageIdx);
        let nextIds: number[];
        if (exists) {
          if (selectedPageIds.length === 1) return;
          nextIds = selectedPageIds.filter((id) => id !== pageIdx);
        } else {
          nextIds = [...selectedPageIds, pageIdx];
        }
        setSelectedPageIds(nextIds);
        if (nextIds.length === 1) selectPage(nextIds[0]);
      } else if (event.shiftKey && rangeAnchorRef.current !== null) {
        const from = Math.min(rangeAnchorRef.current, pageIdx);
        const to = Math.max(rangeAnchorRef.current, pageIdx);
        const range: number[] = [];
        for (let i = from; i <= to; i++) {
          range.push(i);
        }
        setSelectedPageIds(range);
        if (range.length === 1) selectPage(range[0]);
      } else {
        selectPage(pageIdx);
        setSelectedPageIds([pageIdx]);
      }
      rangeAnchorRef.current = pageIdx;
    },
    [selectPage, selectedPageIds]
  );

  const handleSelectAllPages = useCallback(() => {
    setSelectedPageIds(pages.map((page) => page.index));
  }, [pages]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
        const inSidebar = document.activeElement?.closest?.(".sidebar-container");
        if (inSidebar) {
          event.preventDefault();
          handleSelectAllPages();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSelectAllPages]);

  const resolveContextTargets = useCallback(
    (idx: number) =>
      selectedPageIds.length > 1 && selectedPageIds.includes(idx) ? [...selectedPageIds] : [idx],
    [selectedPageIds]
  );

  return {
    selectedPageIds,
    setSelectedPageIds,
    handlePageSelection,
    handleSelectAllPages,
    resolveContextTargets,
  };
}
