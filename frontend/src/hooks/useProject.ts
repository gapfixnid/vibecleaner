import { useCallback, useState } from "react";
import * as api from "../services/api";
import * as desktop from "../services/desktop";
import type { RunTask } from "./useProcessingTask";
import type { ShowToast } from "./useToasts";
import { APP_NAME } from "../appMeta";

export interface OpenFilesResult {
  beforeCount: number;
  afterCount: number;
  addedCount: number;
}

interface UseProjectDeps {
  runTask: RunTask;
  /** Non-blocking success feedback (errors still go through runTask's dialog). */
  showToast: ShowToast;
  loadPagesFromServer: (selectIndex?: number) => Promise<void>;
  /** Mark the project as having unsaved changes. */
  markDirty: () => void;
  /** Mark the project as saved/clean (after save, load, or new). */
  markClean: () => void;
  /** Returns the current sidebar multi-selection (page indices) for persistence. */
  getSelectedIndices: () => number[];
  t?: (key: string) => string;
}

/** Owns file open / project new / load / save flows and the current project path. */
export function useProject({
  runTask,
  showToast,
  loadPagesFromServer,
  markDirty,
  markClean,
  getSelectedIndices,
  t = (key) => key,
}: UseProjectDeps) {
  // Path of the currently-open .vibe project (null = unsaved/new project).
  // Used so "Save Project" writes back to the same file without re-prompting.
  const [currentProjectPath, setCurrentProjectPath] = useState<string | null>(null);

  const handleOpenFiles = useCallback(async (): Promise<OpenFilesResult | undefined> => {
    let result: OpenFilesResult | undefined;
    await runTask(
      t("project.loadingSelectedImages"),
      async () => {
        const files = await desktop.selectMultipleFiles({
          title: t("project.selectMangaImagesTitle"),
          filters: [
            [t("project.mangaImagesFilter"), ["png", "jpg", "jpeg", "webp", "bmp"]],
            [t("project.allFilesFilter"), ["*"]],
          ],
        });
        if (!files || files.length === 0) return; // Cancelled
        const beforeData = await api.getPages();
        const beforeCount = beforeData.pages.length;
        const data = await api.openFiles(files);
        if (data.status === "cancelled") return;
        await loadPagesFromServer();
        const afterData = await api.getPages();
        const addedCount = afterData.pages.length - beforeCount;
        result = {
          beforeCount,
          afterCount: afterData.pages.length,
          addedCount,
        };
        // Importing images mutates the project.
        if (addedCount > 0) markDirty();
      },
      { errorTitle: t("project.failedToOpenFiles"), skipBusy: true }
    );
    return result;
  }, [runTask, loadPagesFromServer, markDirty, t]);

  /** Reset to an empty project. Returns true on success. */
  const handleNewProject = useCallback(async (): Promise<boolean> => {
    let ok = false;
    await runTask(
      t("project.creatingNewProject"),
      async () => {
        await api.newProject();
        await loadPagesFromServer(-1);
        setCurrentProjectPath(null);
        markClean();
        ok = true;
      },
      { errorTitle: t("project.failedToCreateNewProject"), skipBusy: true }
    );
    return ok;
  }, [runTask, loadPagesFromServer, markClean, t]);

  /** Open an existing project. Returns the restored sidebar selection
   *  (page indices) on success, or null on cancel/error. */
  const handleLoadProject = useCallback(async (): Promise<number[] | null> => {
    let restoredSelection: number[] | null = null;
    await runTask(
      t("project.loadingProject"),
      async () => {
        const file = await desktop.selectFile({
          title: t("project.openProjectTitle").replace("{appName}", APP_NAME),
          filters: [
            [t("project.projectFilter").replace("{appName}", APP_NAME), ["vibe"]],
            [t("project.legacyJsonProjectFilter"), ["json"]],
            [t("project.allFilesFilter"), ["*"]],
          ],
        });
        if (!file) return; // Cancelled
        const data = await api.loadProject(file);
        if (data.status === "cancelled") return;
        const restoredIndex = typeof data.current_index === "number" ? data.current_index : 0;
        const selected =
          Array.isArray(data.selected_indices) && data.selected_indices.length > 0
            ? data.selected_indices
            : [restoredIndex];
        await loadPagesFromServer(restoredIndex);
        setCurrentProjectPath(file);
        markClean();
        restoredSelection = selected;
      },
      { errorTitle: t("project.failedToLoadProject"), skipBusy: true }
    );
    return restoredSelection;
  }, [runTask, loadPagesFromServer, markClean, t]);

  /** Save the project. Saves to the known path if set, otherwise prompts.
   *  Returns true if the project was actually written (false on cancel/error). */
  const handleSaveProject = useCallback(async (): Promise<boolean> => {
    let saved = false;
    await runTask(
      t("project.savingProject"),
      async () => {
        let file = currentProjectPath;
        if (!file) {
          file = await desktop.saveFile({
            title: t("project.saveProjectTitle").replace("{appName}", APP_NAME),
            defaultExt: ".vibe",
            filters: [[t("project.projectFilter").replace("{appName}", APP_NAME), ["vibe"]]],
          });
        }
        if (!file) return; // Cancelled
        const data = await api.saveProject(file, getSelectedIndices());
        if (data.status === "cancelled") return;
        setCurrentProjectPath(file);
        markClean();
        saved = true;
        showToast("success", t("project.projectSaved"));
      },
      { errorTitle: t("project.failedToSaveProject"), skipBusy: true }
    );
    return saved;
  }, [runTask, showToast, currentProjectPath, markClean, getSelectedIndices, t]);

  return {
    currentProjectPath,
    handleOpenFiles,
    handleNewProject,
    handleLoadProject,
    handleSaveProject,
  };
}
