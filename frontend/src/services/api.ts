import { api } from "../api";
import type {
  Settings,
  PagesResponse,
  BubblesResponse,
  BubbleUpdate,
  JobStatus,
  CurrentIndexResult,
  ActionResult,
  ExportResult,
  TranslationModelsResponse,
  LoadProjectResult,
  PageInfo,
  BubbleInfo,
} from "../types";

let BACKEND_URL = "http://127.0.0.1:8000";

export const setBackendUrl = (url: string) => {
  BACKEND_URL = url;
};

export const getBackendUrl = () => BACKEND_URL;

export const getSettings = async (): Promise<Settings> => {
  const settings = await api.getSettings();
  return settings as Settings;
};

export const updateSettings = async (settings: Settings): Promise<Settings> => {
  const updated = await api.updateSettings(settings);
  return updated as Settings;
};

export const getPages = async (): Promise<PagesResponse> => {
  const project = await api.getProject();
  const pages: PageInfo[] = project.pages.map((p) => ({
    page_id: p.id,
    index: p.index,
    file_path: p.file_path,
    filename: p.filename,
    width: p.width,
    height: p.height,
    bubble_count: p.bubble_count ?? 0,
    translated_count: p.translated_count ?? 0,
    has_inpaint: p.status === "success" || p.status === "warning",
  }));
  return {
    pages,
    current_index: project.pages.findIndex((p) => p.id === project.current_page_id),
  };
};

export const getBubbles = async (pageId: string): Promise<BubblesResponse> => {
  const page = await api.getPage(pageId);
  const bubbles: BubbleInfo[] = page.bubbles.map((b) => ({
    id: parseInt(b.id.replace("bubble_", "")) || 0,
    x: b.bubbleBox.x,
    y: b.bubbleBox.y,
    width: b.bubbleBox.width,
    height: b.bubbleBox.height,
    text: b.text,
    translated: b.translated,
    font_family: b.style.font_family,
    font_size: b.style.font_size,
    computed_font_size: b.style.computed_font_size || 12,
    bold: b.style.bold,
    italic: b.style.italic,
    color: b.style.color,
    alignment: b.style.alignment,
    text_class: b.text_class || "",
    lines: b.layout.lines.map((l) => ({
      text: l.text,
      x: l.x,
      y: l.y,
      width: l.width,
      height: l.height,
    })),
  }));
  return { bubbles };
};

export const selectPage = async (idx: number, pageId?: string): Promise<ActionResult> => {
  const res = await api.selectPage(idx, pageId);
  return { status: "success", ...res };
};

export const duplicatePage = async (idx: number, pageId?: string): Promise<CurrentIndexResult> => {
  return api.duplicatePage(idx, pageId);
};

export const duplicatePagesBatch = async (indices: number[], pageIds?: string[]): Promise<CurrentIndexResult> => {
  return api.duplicatePagesBatch(indices, pageIds);
};

export const deletePage = async (idx: number, pageId?: string): Promise<CurrentIndexResult> => {
  return api.deletePage(idx, pageId);
};

export const deletePagesBatch = async (indices: number[], pageIds?: string[]): Promise<CurrentIndexResult> => {
  return api.deletePagesBatch(indices, pageIds);
};

export const reorderPages = async (fromIdx: number, toIdx: number): Promise<CurrentIndexResult> => {
  return api.reorderPages(fromIdx, toIdx);
};

export const renamePage = async (pageId: string, name: string): Promise<ActionResult> => {
  const res = await api.renamePage(pageId, name);
  return { status: "success", ...res };
};

export const openDirectory = async (directory: string): Promise<ActionResult> => {
  await api.importDirectory(directory);
  return { status: "success" };
};

export const openFiles = async (files: string[]): Promise<ActionResult> => {
  await api.importImages(files);
  return { status: "success" };
};

export const newProject = async (): Promise<ActionResult> => {
  const res = await api.newProject();
  return { status: "success", ...res };
};

export const loadProject = async (filePath: string): Promise<LoadProjectResult> => {
  const res = await api.loadProject(filePath);
  return { status: "success", ...res };
};

export const saveProject = async (filePath: string, selectedIndices: number[] = []): Promise<ActionResult> => {
  const res = await api.saveProject(filePath, selectedIndices);
  return { status: "success", ...res };
};

export const inpaint = async (pageId: string): Promise<JobStatus> => {
  return api.inpaint(pageId) as Promise<JobStatus>;
};

export const translateAll = async (pageId: string): Promise<JobStatus> => {
  return api.translateAll(pageId) as Promise<JobStatus>;
};

export const translateBatch = async (pageIndices?: number[], pageIds?: string[]): Promise<JobStatus> => {
  return api.translateBatch(pageIndices, pageIds) as Promise<JobStatus>;
};

export const getJob = async (jobId: string): Promise<JobStatus> => {
  return api.getJob(jobId) as Promise<JobStatus>;
};

export const exportPage = async (pageId: string, formData: FormData): Promise<ExportResult> => {
  const savePath = formData.get("save_path") as string;
  if (!savePath) {
    throw new Error("save_path is required");
  }
  const res = await api.exportPageToPath(pageId, savePath);
  return { status: "success", saved_path: res.saved_path || savePath };
};

export const updateBubbles = async (pageId: string, bubbles: BubbleUpdate[]): Promise<ActionResult> => {
  const res = await api.updateBubbles(pageId, bubbles);
  return { status: "success", ...res };
};

export const reOcrBubble = async (pageId: string, bubbleId: number): Promise<ActionResult> => {
  await api.reocrBubble(pageId, `bubble_${bubbleId}`);
  return { status: "success" };
};

export const translateBubble = async (pageId: string, bubbleId: number): Promise<JobStatus> => {
  await api.retranslateBubble(pageId, `bubble_${bubbleId}`);
  return { job_id: `translate_bubble_${bubbleId}`, status: "succeeded" };
};

export const inpaintBubble = async (pageId: string, bubbleId: number): Promise<JobStatus> => {
  await api.autofitBubble(pageId, `bubble_${bubbleId}`);
  return { job_id: `inpaint_bubble_${bubbleId}`, status: "succeeded" };
};

export const getTranslationModels = async (
  provider: string,
  apiKey: string,
  baseUrl: string
): Promise<TranslationModelsResponse> => {
  const res = await api.getTranslationModels(provider, apiKey, baseUrl);
  return {
    provider: res.provider,
    models: res.models,
    error: res.error,
  };
};
