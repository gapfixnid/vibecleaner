import type { BubbleInfo, BubbleUpdate, PageInfo, PagesResponse } from "../types";
import type { BubbleUpdateDto } from "../types/api";
import type { BubbleDto } from "../types/bubble";
import type { PageDto, ProjectDto } from "../types/project";

function hasInpaintedPreview(page: PageDto): boolean {
  return page.has_inpaint ?? (
    page.status === "success" ||
    page.status === "warning" ||
    page.status === "ready_for_review" ||
    page.status === "has_warnings"
  );
}

export function toPageInfo(page: PageDto): PageInfo {
  return {
    page_id: page.id,
    index: page.index,
    file_path: page.file_path,
    filename: page.filename,
    width: page.width,
    height: page.height,
    bubble_count: page.bubble_count ?? 0,
    translated_count: page.translated_count ?? 0,
    has_inpaint: hasInpaintedPreview(page),
    status: page.status,
    problems: page.problems ?? [],
  };
}

export function toPagesResponse(project: ProjectDto): PagesResponse {
  return {
    pages: project.pages.map(toPageInfo),
    current_index: project.pages.findIndex((page) => page.id === project.current_page_id),
  };
}

export function toBubbleInfo(bubble: BubbleDto): BubbleInfo {
  return {
    id: parseInt(bubble.id.replace("bubble_", "")) || 0,
    x: bubble.bubbleBox.x,
    y: bubble.bubbleBox.y,
    width: bubble.bubbleBox.width,
    height: bubble.bubbleBox.height,
    text: bubble.text,
    translated: bubble.translated,
    font_family: bubble.style.font_family,
    computed_font_family: bubble.style.computed_font_family || "",
    font_size: bubble.style.font_size,
    font_mode: bubble.style.font_mode ?? (bubble.style.font_size > 0 ? "fixed" : "auto"),
    requested_font_size: bubble.style.requested_font_size ?? (
      bubble.style.font_size > 0 ? bubble.style.font_size : null
    ),
    computed_font_size: bubble.style.computed_font_size || 12,
    bold: bubble.style.bold,
    italic: bubble.style.italic,
    color: bubble.style.color,
    alignment: bubble.style.alignment,
    text_class: bubble.text_class || "",
    status: bubble.status,
    problems: bubble.problems ?? [],
    edited: Boolean(bubble.edited),
    layout_overflow: Boolean(bubble.layout.overflow),
    writing_mode: bubble.layout.writing_mode || "horizontal",
    text_direction: bubble.layout.text_direction || "ltr",
    justification: bubble.layout.justification || "none",
    layout_padding: bubble.layout.padding || {},
    layout_margin: bubble.layout.margin || {},
    layout_confidence: bubble.layout.confidence || 0,
    layout_reasoning: bubble.layout.reasoning || "",
    text_box: bubble.textBox ? {
      x: bubble.textBox.x,
      y: bubble.textBox.y,
      width: bubble.textBox.width,
      height: bubble.textBox.height,
    } : null,
    lines: bubble.layout.lines.map((line) => ({
      text: line.text,
      x: line.x,
      y: line.y,
      width: line.width,
      height: line.height,
    })),
  };
}

export function toBubbleUpdateDto(bubble: BubbleUpdate): BubbleUpdateDto {
  return {
    id: bubble.id,
    x: bubble.x,
    y: bubble.y,
    width: bubble.width,
    height: bubble.height,
    text: bubble.text,
    translated: bubble.translated,
    font_family: bubble.font_family,
    // font_size remains the persisted compatibility field: zero selects
    // automatic fitting and a positive value selects fixed mode.
    font_size: bubble.font_size,
    bold: bubble.bold,
    italic: bubble.italic,
    color: bubble.color,
    alignment: bubble.alignment,
  };
}
