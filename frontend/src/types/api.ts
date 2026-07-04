import type { ProjectDto, PageDto, SettingsDto } from "./project";
import type { BubbleDto, BubblePatchDto } from "./bubble";
import type { PipelineTargetDto, PipelineProgressDto } from "./pipeline";

export interface ActionResultDto {
  status?: string;
  [key: string]: unknown;
}

export interface CurrentIndexResultDto {
  current_index: number;
  [key: string]: unknown;
}

export interface LoadProjectResultDto {
  status?: string;
  page_count?: number;
  current_index?: number;
  selected_indices?: number[];
}

export type JobStateDto = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface JobStatusDto {
  job_id: string;
  kind?: string;
  page_idx?: number;
  status: JobStateDto;
  progress?: number;
  message?: string;
  result?: unknown;
  error?: string;
}

export interface BubbleUpdateDto {
  id: number;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  translated: string;
  font_family: string;
  font_size: number;
  bold: boolean;
  italic: boolean;
  color: string;
  alignment: string;
}

export interface AddBubbleResultDto {
  status?: string;
  bubble_id: number;
  text?: string;
}

export interface ExportPageResultDto {
  status?: string;
  saved_path?: string;
}

export interface ExportOptionsDto {
  page_ids: string[];
  format: "png" | "jpg" | "pdf";
  output_dir: string;
}

export interface ExportResultDto {
  success: boolean;
  exported_paths: string[];
  problems: string[];
}

export interface TranslationModelsDto {
  provider: string;
  models: string[];
  error?: string;
}

export interface ModelRequirementDto {
  id: string;
  category: string;
  label: string;
  downloaded: boolean;
  files: string[];
  path: string;
}

export interface ModelStatusDto {
  setup_completed: boolean;
  required: ModelRequirementDto[];
  missing: ModelRequirementDto[];
  required_count: number;
  missing_count: number;
  all_ready: boolean;
}

export interface vibeCleanerApi {
  importImages(paths?: string[]): Promise<ProjectDto>;
  importDirectory(directory: string): Promise<ProjectDto>;
  getProject(): Promise<ProjectDto>;
  getPage(pageId: string): Promise<PageDto>;
  newProject(): Promise<ActionResultDto>;
  loadProject(filePath: string): Promise<LoadProjectResultDto>;
  saveProject(filePath: string, selectedIndices?: number[]): Promise<ActionResultDto>;
  selectPage(index?: number, pageId?: string): Promise<CurrentIndexResultDto>;
  duplicatePage(index?: number, pageId?: string): Promise<CurrentIndexResultDto>;
  duplicatePagesBatch(pageIndices?: number[], pageIds?: string[]): Promise<CurrentIndexResultDto>;
  deletePage(index?: number, pageId?: string): Promise<CurrentIndexResultDto>;
  deletePagesBatch(pageIndices?: number[], pageIds?: string[]): Promise<CurrentIndexResultDto>;
  reorderPages(fromIndex: number, toIndex: number): Promise<CurrentIndexResultDto>;
  renamePage(pageId: string, name: string): Promise<ActionResultDto>;
  inpaint(pageId: string): Promise<JobStatusDto>;
  translateAll(pageId: string): Promise<JobStatusDto>;
  translateBatch(pageIndices?: number[], pageIds?: string[]): Promise<JobStatusDto>;
  getJob(jobId: string): Promise<JobStatusDto>;
  cancelJob(jobId: string): Promise<JobStatusDto>;
  runAutoTypeset(
    target: PipelineTargetDto,
    onProgress?: (progress: PipelineProgressDto) => void
  ): Promise<PageDto>;
  updateBubbles(pageId: string, bubbles: BubbleUpdateDto[]): Promise<ActionResultDto>;
  updateBubble(pageId: string, bubbleId: string, patch: BubblePatchDto): Promise<BubbleDto>;
  layoutBubble(pageId: string, bubbleId: string): Promise<BubbleDto>;
  reocrBubble(pageId: string, bubbleId: string): Promise<BubbleDto>;
  retranslateBubble(pageId: string, bubbleId: string): Promise<BubbleDto>;
  autofitBubble(pageId: string, bubbleId: string): Promise<BubbleDto>;
  deleteBubble(pageId: string, bubbleId: string): Promise<PageDto>;
  exportPageToPath(pageId: string, savePath: string): Promise<ExportPageResultDto>;
  exportPages(options: ExportOptionsDto): Promise<ExportResultDto>;
  getSettings(): Promise<SettingsDto>;
  updateSettings(settings: SettingsDto): Promise<SettingsDto>;
  getModelStatus(): Promise<ModelStatusDto>;
  downloadRequiredModels(): Promise<JobStatusDto>;
  getTranslationModels(provider: string, apiKey: string, baseUrl: string): Promise<TranslationModelsDto>;
}

export class ApiError extends Error {
  public code: string;
  public details?: unknown;

  constructor(code: string, message: string, details?: unknown) {
    super(message);
    this.code = code;
    this.details = details;
    this.name = "ApiError";
  }
}
