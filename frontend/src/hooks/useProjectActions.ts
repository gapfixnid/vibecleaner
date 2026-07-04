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
    onDiscard: () => void,
    labels?: { save?: string; dontSave?: string; cancel?: string }
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
  t?: (key: string) => string;
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
  t = (key) => key,
}: UseProjectActionsDeps) {
  const guardUnsaved = useCallback(
    (proceed: () => void) => {
      if (!isDirty) {
        proceed();
        return;
      }
      showUnsavedPrompt(
        t("project.unsavedChanges"),
        t("project.unsavedChangesMessage"),
        async () => {
          const saved = await saveProject();
          if (saved) proceed();
        },
        () => proceed(),
        {
          save: t("dialog.save"),
          dontSave: t("dialog.dontSave"),
          cancel: t("dialog.cancel"),
        }
      );
    },
    [isDirty, showUnsavedPrompt, saveProject, t]
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
        t("project.renamingPage"),
        async () => {
          await api.renamePage(pageId, name);
          await loadPagesFromServer(currentIndexRef.current, { skipPageActivation: true });
          markDirty();
        },
        { errorTitle: t("project.renameFailed") }
      );
    },
    [pages, runTask, loadPagesFromServer, currentIndexRef, markDirty, t]
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
