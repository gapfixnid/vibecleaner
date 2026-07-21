import { invoke } from "@tauri-apps/api/core";
import { ApiError } from "../types/api";
import type {
  ActionResultDto,
  BubbleUpdateDto,
  CurrentIndexResultDto,
  ExportOptionsDto,
  ExportPageResultDto,
  ExportResultDto,
  JobStatusDto,
  LoadProjectResultDto,
  ModelStatusDto,
  TranslationModelsDto,
  vibeCleanerApi,
} from "../types/api";
import type { ProviderCatalogDto } from "../types/provider";
import type { ProjectDto, PageDto, SettingsDto } from "../types/project";
import type { BubbleDto, BubblePatchDto } from "../types/bubble";

async function callTauri<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(cmd, args);
  } catch (err: unknown) {
    const details = typeof err === "object" && err !== null ? err as Record<string, unknown> : null;
    const msg = typeof err === "string"
      ? err
      : typeof details?.message === "string" ? details.message : String(err);
    const code = typeof details?.code === "string" ? details.code : "TAURI_ERROR";
    throw new ApiError(code, msg, err);
  }
}

export const tauriClient: vibeCleanerApi = {
  async importImages(paths?: string[]): Promise<ProjectDto> {
    return callTauri<ProjectDto>("import_images", { paths });
  },

  async importDirectory(directory: string): Promise<ProjectDto> {
    return callTauri<ProjectDto>("import_directory", { directory });
  },

  async getProject(): Promise<ProjectDto> {
    return callTauri<ProjectDto>("get_project");
  },

  async getPage(pageId: string): Promise<PageDto> {
    return callTauri<PageDto>("get_page", { pageId });
  },

  async newProject(): Promise<ActionResultDto> {
    return callTauri<ActionResultDto>("new_project");
  },

  async loadProject(filePath: string): Promise<LoadProjectResultDto> {
    return callTauri<LoadProjectResultDto>("load_project", { filePath });
  },

  async saveProject(filePath: string, selectedIndices: number[] = []): Promise<ActionResultDto> {
    return callTauri<ActionResultDto>("save_project", { filePath, selectedIndices });
  },

  async selectPage(index?: number, pageId?: string): Promise<CurrentIndexResultDto> {
    return callTauri<CurrentIndexResultDto>("select_page", { index, pageId });
  },

  async duplicatePage(index?: number, pageId?: string): Promise<CurrentIndexResultDto> {
    return callTauri<CurrentIndexResultDto>("duplicate_page", { index, pageId });
  },

  async duplicatePagesBatch(pageIndices?: number[], pageIds?: string[]): Promise<CurrentIndexResultDto> {
    return callTauri<CurrentIndexResultDto>("duplicate_pages_batch", { pageIndices, pageIds });
  },

  async deletePage(index?: number, pageId?: string): Promise<CurrentIndexResultDto> {
    return callTauri<CurrentIndexResultDto>("delete_page", { index, pageId });
  },

  async deletePagesBatch(pageIndices?: number[], pageIds?: string[]): Promise<CurrentIndexResultDto> {
    return callTauri<CurrentIndexResultDto>("delete_pages_batch", { pageIndices, pageIds });
  },

  async reorderPages(fromIndex: number, toIndex: number): Promise<CurrentIndexResultDto> {
    return callTauri<CurrentIndexResultDto>("reorder_pages", { fromIndex, toIndex });
  },

  async renamePage(pageId: string, name: string): Promise<ActionResultDto> {
    return callTauri<ActionResultDto>("rename_page", { pageId, name });
  },

  async inpaint(pageId: string): Promise<JobStatusDto> {
    return callTauri<JobStatusDto>("inpaint_page", { pageId });
  },

  async translateAll(pageId: string): Promise<JobStatusDto> {
    return callTauri<JobStatusDto>("translate_all_page", { pageId });
  },

  async translateBatch(pageIndices?: number[], pageIds?: string[]): Promise<JobStatusDto> {
    return callTauri<JobStatusDto>("translate_batch", { pageIndices, pageIds });
  },

  async getJob(jobId: string): Promise<JobStatusDto> {
    return callTauri<JobStatusDto>("get_job", { jobId });
  },

  async cancelJob(jobId: string): Promise<JobStatusDto> {
    return callTauri<JobStatusDto>("cancel_job", { jobId });
  },

  async updateBubbles(pageId: string, bubbles: BubbleUpdateDto[]): Promise<ActionResultDto> {
    return callTauri<ActionResultDto>("update_bubbles", { pageId, bubbles });
  },

  async updateBubble(pageId: string, bubbleId: string, patch: BubblePatchDto): Promise<BubbleDto> {
    return callTauri<BubbleDto>("update_bubble", { pageId, bubbleId, patch });
  },

  async layoutBubble(pageId: string, bubbleId: string): Promise<BubbleDto> {
    return callTauri<BubbleDto>("layout_bubble", { pageId, bubbleId });
  },

  async reocrBubble(pageId: string, bubbleId: string): Promise<BubbleDto> {
    return callTauri<BubbleDto>("reocr_bubble", { pageId, bubbleId });
  },

  async retranslateBubble(pageId: string, bubbleId: string): Promise<BubbleDto> {
    return callTauri<BubbleDto>("retranslate_bubble", { pageId, bubbleId });
  },

  async autofitBubble(pageId: string, bubbleId: string): Promise<BubbleDto> {
    return callTauri<BubbleDto>("autofit_bubble", { pageId, bubbleId });
  },

  async deleteBubble(pageId: string, bubbleId: string): Promise<PageDto> {
    return callTauri<PageDto>("delete_bubble", { pageId, bubbleId });
  },

  async exportPageToPath(pageId: string, savePath: string): Promise<ExportPageResultDto> {
    return callTauri<ExportPageResultDto>("export_page_to_path", { pageId, savePath });
  },

  async exportPages(options: ExportOptionsDto): Promise<ExportResultDto> {
    return callTauri<ExportResultDto>("export_pages", { options });
  },

  async getSettings(): Promise<SettingsDto> {
    return callTauri<SettingsDto>("get_settings");
  },

  async getProviderCatalog(): Promise<ProviderCatalogDto> {
    return callTauri<ProviderCatalogDto>("get_provider_catalog");
  },

  async updateSettings(settings: SettingsDto): Promise<SettingsDto> {
    return callTauri<SettingsDto>("update_settings", { settings });
  },

  async getModelStatus(): Promise<ModelStatusDto> {
    return callTauri<ModelStatusDto>("get_model_status");
  },

  async downloadRequiredModels(): Promise<JobStatusDto> {
    return callTauri<JobStatusDto>("download_required_models");
  },

  async getTranslationModels(provider: string, apiKey: string, baseUrl: string): Promise<TranslationModelsDto> {
    return callTauri<TranslationModelsDto>("get_translation_models", { provider, apiKey, baseUrl });
  },
};
