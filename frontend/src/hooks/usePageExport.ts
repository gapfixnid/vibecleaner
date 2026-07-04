import { useCallback } from "react";
import * as api from "../services/api";
import * as desktop from "../services/desktop";
import type { BubbleInfo, PageInfo } from "../types";
import type { RunTask, WaitForJob } from "./useProcessingTask";

interface UsePageExportDeps {
  pages: PageInfo[];
  runTask: RunTask;
  waitForJob: WaitForJob;
  syncBubblesToBackend: (bubblesList?: BubbleInfo[], opts?: { silent?: boolean }) => Promise<void>;
  bumpPageVersion: (idx: number) => void;
  loadPagesFromServer: (selectIndex?: number, options?: { skipPageActivation?: boolean }) => Promise<void>;
  showAlert: (type: "success" | "error" | "warning" | "info", title: string, message: string) => void;
  t?: (key: string) => string;
}

function deriveExportBaseName(filename: string | undefined, idx: number): string {
  if (!filename) return `page_${idx + 1}`;
  const dot = filename.lastIndexOf(".");
  const base = dot > 0 ? filename.slice(0, dot) : filename;
  return base.trim() || `page_${idx + 1}`;
}

export function usePageExport({
  pages,
  runTask,
  waitForJob,
  syncBubblesToBackend,
  bumpPageVersion,
  loadPagesFromServer,
  showAlert,
  t = (key) => key,
}: UsePageExportDeps) {
  const exportPageToPath = useCallback(
    async (idx: number, savePath: string) => {
      const pageId = pages[idx]?.page_id;
      if (!pageId) throw new Error("Page ID not found");
      if (!pages[idx]?.has_inpaint) {
        const job = await api.inpaint(pageId);
        await waitForJob(job, t("export.cleaningBeforeExport"));
        bumpPageVersion(idx);
        await loadPagesFromServer(idx);
      }
      const formData = new FormData();
      formData.append("save_path", savePath);
      formData.append("use_dialog", "false");
      return api.exportPage(pageId, formData);
    },
    [pages, waitForJob, bumpPageVersion, loadPagesFromServer, t]
  );

  const handleExportPages = useCallback(
    async (ids: number[]) => {
      const targets = Array.from(new Set(ids))
        .filter((idx) => idx >= 0 && idx < pages.length)
        .sort((a, b) => a - b);
      if (targets.length === 0) return;

      if (targets.length === 1) {
        const idx = targets[0];
        const file = await desktop.saveFile({
          title: t("export.pageImageTitle"),
          defaultExt: ".png",
          filters: [
            [t("export.pngImageFilter"), ["png"]],
            [t("export.jpegImageFilter"), ["jpg", "jpeg"]],
            [t("export.webpImageFilter"), ["webp"]],
          ],
        });
        if (!file) return;
        await runTask(
          t("export.exportingPage"),
          async () => {
            await syncBubblesToBackend(undefined, { silent: true });
            const data = await exportPageToPath(idx, file);
            if (data.status === "cancelled") return;
            showAlert("success", t("export.successTitle"), t("export.successSingleMessage").replace("{path}", data.saved_path || ""));
          },
          { errorTitle: t("export.failedTitle") }
        );
        return;
      }

      const dir = await desktop.selectDirectory();
      if (!dir) return;
      await runTask(
        t("export.exportingPages").replace("{count}", String(targets.length)),
        async () => {
          await syncBubblesToBackend(undefined, { silent: true });
          const usedNames = new Set<string>();
          for (const idx of targets) {
            const base = deriveExportBaseName(pages[idx]?.filename, idx);
            let name = `${base}.png`;
            let suffix = 1;
            while (usedNames.has(name.toLowerCase())) {
              name = `${base}_${suffix++}.png`;
            }
            usedNames.add(name.toLowerCase());
            await exportPageToPath(idx, `${dir}/${name}`);
          }
          showAlert("success", t("export.successTitle"), t("export.successMultiMessage").replace("{count}", String(targets.length)).replace("{path}", dir));
        },
        { errorTitle: t("export.failedTitle") }
      );
    },
    [pages, runTask, syncBubblesToBackend, exportPageToPath, showAlert, t]
  );

  return {
    handleExportPages,
    exportPageToPath,
  };
}
