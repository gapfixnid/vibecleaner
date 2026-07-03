import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import * as api from "../services/api";
import type { PageInfo } from "../types";
import type { RunTask } from "./useProcessingTask";

interface UseProjectActionsDeps {
  isDirty: boolean;
  showUnsavedPrompt: (
    title: string,
    message: string,
    onSave: () => void,
    onDiscard: () => void
  ) => void;
  saveProject: () => Promise<boolean>;
  newProject: () => Promise<boolean>;
  loadProject: () => Promise<number[] | null>;
  openFiles: () => Promise<{ beforeCount: number; afterCount: number; addedCount: number } | undefined>;
  pages: PageInfo[];
  selectedPageIds: number[];
  runTask: RunTask;
  loadPagesFromServer: (selectIndex?: number, options?: { skipPageActivation?: boolean }) => Promise<void>;
  currentIndexRef: MutableRefObject<number>;
  markDirty: () => void;
  resetPageVersions: () => void;
  selectPage: (idx: number) => void;
  deletePages: (indices: number[]) => void;
  setSelectedPageIds: Dispatch<SetStateAction<number[]>>;
  setSelectedBubbleId: Dispatch<SetStateAction<number | null>>;
}

export function useProjectActions({
  isDirty,
  showUnsavedPrompt,
  saveProject,
  newProject,
  loadProject,
  openFiles,
  pages,
  selectedPageIds,
  runTask,
  loadPagesFromServer,
  currentIndexRef,
  markDirty,
  resetPageVersions,
  selectPage,
  deletePages,
  setSelectedPageIds,
  setSelectedBubbleId,
}: UseProjectActionsDeps) {
  const guardUnsaved = useCallback(
    (proceed: () => void) => {
      if (!isDirty) {
        proceed();
        return;
      }
      showUnsavedPrompt(
        "Unsaved Changes",
        "You have unsaved changes. Do you want to save them before continuing?",
        async () => {
          const saved = await saveProject();
          if (saved) proceed();
        },
        () => proceed()
      );
    },
    [isDirty, showUnsavedPrompt, saveProject]
  );

  const handleNewProject = useCallback(() => {
    guardUnsaved(async () => {
      const ok = await newProject();
      if (ok) {
        resetPageVersions();
        setSelectedPageIds([]);
        setSelectedBubbleId(null);
      }
    });
  }, [guardUnsaved, newProject, resetPageVersions, setSelectedPageIds, setSelectedBubbleId]);

  const handleOpenProject = useCallback(() => {
    guardUnsaved(async () => {
      const restoredSelection = await loadProject();
      if (restoredSelection) {
        resetPageVersions();
        setSelectedPageIds(restoredSelection);
        setSelectedBubbleId(null);
      }
    });
  }, [guardUnsaved, loadProject, resetPageVersions, setSelectedPageIds, setSelectedBubbleId]);

  const handleImportImages = useCallback(async () => {
    const result = await openFiles();
    if (!result) return;
    const { beforeCount, afterCount, addedCount } = result;
    if (beforeCount === 0 && addedCount > 0) {
      selectPage(0);
      setSelectedPageIds([0]);
    } else if (addedCount === 1) {
      const newIndex = afterCount - 1;
      selectPage(newIndex);
      setSelectedPageIds([newIndex]);
    }
  }, [openFiles, selectPage, setSelectedPageIds]);

  const handleDeletePage = useCallback(
    (idx: number) => {
      const isSelected = selectedPageIds.length > 1 && selectedPageIds.includes(idx);
      deletePages(isSelected ? selectedPageIds : [idx]);
    },
    [deletePages, selectedPageIds]
  );

  const handleRenamePage = useCallback(
    async (idx: number, name: string) => {
      const pageId = pages[idx]?.page_id;
      if (!pageId) return;
      await runTask(
        "Renaming page...",
        async () => {
          await api.renamePage(pageId, name);
          await loadPagesFromServer(currentIndexRef.current, { skipPageActivation: true });
          markDirty();
        },
        { errorTitle: "Rename Failed" }
      );
    },
    [pages, runTask, loadPagesFromServer, currentIndexRef, markDirty]
  );

  return {
    guardUnsaved,
    handleNewProject,
    handleOpenProject,
    handleImportImages,
    handleDeletePage,
    handleRenamePage,
  };
}
