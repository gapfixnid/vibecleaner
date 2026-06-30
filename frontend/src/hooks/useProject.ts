import { useCallback, useState } from "react";
import * as api from "../services/api";
import * as desktop from "../services/desktop";
import type { RunTask } from "./useProcessingTask";
import type { AlertType } from "./useDialog";
import { APP_NAME } from "../appMeta";

export interface OpenFilesResult {
  beforeCount: number;
  afterCount: number;
  addedCount: number;
}

interface UseProjectDeps {
  runTask: RunTask;
  showAlert: (type: AlertType, title: string, message: string) => void;
  loadPagesFromServer: (selectIndex?: number) => Promise<void>;
  /** Mark the project as having unsaved changes. */
  markDirty: () => void;
  /** Mark the project as saved/clean (after save, load, or new). */
  markClean: () => void;
  /** Returns the current sidebar multi-selection (page indices) for persistence. */
  getSelectedIndices: () => number[];
}

/** Owns file open / project new / load / save flows and the current project path. */
export function useProject({
  runTask,
  showAlert,
  loadPagesFromServer,
  markDirty,
  markClean,
  getSelectedIndices,
}: UseProjectDeps) {
  // Path of the currently-open .vibe project (null = unsaved/new project).
  // Used so "Save Project" writes back to the same file without re-prompting.
  const [currentProjectPath, setCurrentProjectPath] = useState<string | null>(null);

  const handleOpenFiles = useCallback(async (): Promise<OpenFilesResult | undefined> => {
    let result: OpenFilesResult | undefined;
    await runTask(
      "Loading selected images...",
      async () => {
        const files = await desktop.selectMultipleFiles({
          title: "Select Manga Images to Load",
          filters: [
            ["Manga Images", ["png", "jpg", "jpeg", "webp", "bmp"]],
            ["All Files", ["*"]],
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
      { errorTitle: "Failed to Open Files", skipBusy: true }
    );
    return result;
  }, [runTask, loadPagesFromServer, markDirty]);

  /** Reset to an empty project. Returns true on success. */
  const handleNewProject = useCallback(async (): Promise<boolean> => {
    let ok = false;
    await runTask(
      "Creating new project...",
      async () => {
        await api.newProject();
        await loadPagesFromServer(-1);
        setCurrentProjectPath(null);
        markClean();
        ok = true;
      },
      { errorTitle: "Failed to Create New Project", skipBusy: true }
    );
    return ok;
  }, [runTask, loadPagesFromServer, markClean]);

  /** Open an existing project. Returns the restored sidebar selection
   *  (page indices) on success, or null on cancel/error. */
  const handleLoadProject = useCallback(async (): Promise<number[] | null> => {
    let restoredSelection: number[] | null = null;
    await runTask(
      "Loading project...",
      async () => {
        const file = await desktop.selectFile({
          title: `Open ${APP_NAME} Project`,
          filters: [
            [`${APP_NAME} Project`, ["vibe"]],
            ["Legacy JSON Project", ["json"]],
            ["All Files", ["*"]],
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
      { errorTitle: "Failed to Load Project", skipBusy: true }
    );
    return restoredSelection;
  }, [runTask, loadPagesFromServer, markClean]);

  /** Save the project. Saves to the known path if set, otherwise prompts.
   *  Returns true if the project was actually written (false on cancel/error). */
  const handleSaveProject = useCallback(async (): Promise<boolean> => {
    let saved = false;
    await runTask(
      "Saving project...",
      async () => {
        let file = currentProjectPath;
        if (!file) {
          file = await desktop.saveFile({
            title: `Save ${APP_NAME} Project`,
            defaultExt: ".vibe",
            filters: [[`${APP_NAME} Project`, ["vibe"]]],
          });
        }
        if (!file) return; // Cancelled
        const data = await api.saveProject(file, getSelectedIndices());
        if (data.status === "cancelled") return;
        setCurrentProjectPath(file);
        markClean();
        saved = true;
        showAlert("success", "Success", "Project saved successfully!");
      },
      { errorTitle: "Failed to Save Project", skipBusy: true }
    );
    return saved;
  }, [runTask, showAlert, currentProjectPath, markClean, getSelectedIndices]);

  return {
    currentProjectPath,
    handleOpenFiles,
    handleNewProject,
    handleLoadProject,
    handleSaveProject,
  };
}
