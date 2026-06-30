import type { PageDto } from "../types/project";
import type { BubbleDto } from "../types/bubble";
import type { PipelineProgressDto } from "../types/pipeline";

export type PageBadgeKind = "none" | "orange" | "orange-blink" | "green";

export interface PageBadge {
  kind: PageBadgeKind;
  blink: boolean;
  label: string;
}

export function getPageBadge(page: PageDto, pipeline?: PipelineProgressDto): PageBadge {
  if (pipeline && pipeline.stage !== "completed") {
    return { kind: "orange-blink", blink: true, label: pipeline.message || "Processing..." };
  }
  if (page.status === "processing") {
    return { kind: "orange-blink", blink: true, label: "Processing..." };
  }
  if (page.status === "success") {
    return { kind: "green", blink: false, label: "Translated" };
  }
  if (page.status === "warning") {
    return { kind: "orange", blink: false, label: "Warning" };
  }
  return { kind: "none", blink: false, label: "" };
}

export function isPageProcessing(page: PageDto, pipeline?: PipelineProgressDto): boolean {
  return page.status === "processing" || (!!pipeline && pipeline.stage !== "completed");
}

export function getBubbleVisualState(bubble: BubbleDto): "normal" | "warning" | "error" | "processing" {
  if (bubble.problems.includes("TEXT_OVERFLOW")) {
    return "warning";
  }
  if (bubble.problems.includes("TRANSLATE_FAILED") || bubble.problems.includes("OCR_EMPTY")) {
    return "error";
  }
  if (bubble.status === "warning") {
    return "warning";
  }
  if (bubble.status === "error") {
    return "error";
  }
  if (bubble.status === "idle") {
    return "processing";
  }
  return "normal";
}

export interface PageThumbnailVM {
  id: string;
  index: number;
  filename: string;
  filePath: string;
  width: number;
  height: number;
  bubbleCount: number;
  translatedCount: number;
  hasInpaint: boolean;
  badge: PageBadge;
  isProcessing: boolean;
}

export function toPageThumbnailViewModel(page: PageDto, pipeline?: PipelineProgressDto): PageThumbnailVM {
  return {
    id: page.id,
    index: page.index,
    filename: page.filename,
    filePath: page.file_path,
    width: page.width,
    height: page.height,
    bubbleCount: page.bubble_count ?? page.bubbles.length,
    translatedCount: page.translated_count ?? page.bubbles.filter((b) => b.translated).length,
    hasInpaint: page.status === "success" || page.status === "warning" || page.bubbles.some((b) => b.status === "success"),
    badge: getPageBadge(page, pipeline),
    isProcessing: isPageProcessing(page, pipeline),
  };
}

export interface InspectorVM {
  id: string;
  originalText: string;
  translatedText: string;
  fontFamily: string;
  fontSize: number;
  bold: boolean;
  italic: boolean;
  color: string;
  alignment: "left" | "center" | "right";
  status: "normal" | "warning" | "error" | "processing";
  problems: string[];
}

export function toInspectorViewModel(bubble: BubbleDto | null): InspectorVM | null {
  if (!bubble) return null;
  return {
    id: bubble.id,
    originalText: bubble.text,
    translatedText: bubble.translated,
    fontFamily: bubble.style.font_family,
    fontSize: bubble.style.font_size === 0 ? (bubble.style.computed_font_size || 12) : bubble.style.font_size,
    bold: bubble.style.bold,
    italic: bubble.style.italic,
    color: bubble.style.color,
    alignment: bubble.style.alignment,
    status: getBubbleVisualState(bubble),
    problems: bubble.problems,
  };
}
