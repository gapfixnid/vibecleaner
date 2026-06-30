// Centralized shared types used across the UI and the API service layer.

export * from "./types/common";
export * from "./types/bubble";
export * from "./types/project";
export * from "./types/problem";
export * from "./types/pipeline";
export * from "./types/api";

import type { Rect, Point } from "./types/common";
import type { SettingsDto } from "./types/project";

export type { Rect, Point };
export type Settings = SettingsDto;

export interface LineLayout {
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BubbleInfo {
  id: number;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  translated: string;
  font_family: string;
  font_size: number;
  computed_font_size: number;
  bold: boolean;
  italic: boolean;
  color: string;
  alignment: string;
  text_class: string;
  lines: LineLayout[];
}

export interface BubbleUpdate {
  id: number;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  translated: string;
  font_family: string;
  font_size: number;
  computed_font_size: number;
  bold: boolean;
  italic: boolean;
  color: string;
  alignment: string;
}

export interface PageInfo {
  page_id: string;
  index: number;
  file_path: string;
  filename: string;
  width: number;
  height: number;
  bubble_count: number;
  translated_count: number;
  has_inpaint: boolean;
}

export interface AreaDragState {
  mode: "create" | "move" | "resize";
  start: Point;
  initial: Rect;
  hasMoved: boolean;
}

export type JobState = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface JobStatus {
  job_id: string;
  kind?: string;
  page_idx?: number;
  status: JobState;
  progress?: number;
  message?: string;
  result?: any;
  error?: string;
}

export interface PagesResponse {
  pages: PageInfo[];
  current_index: number;
}

export interface BubblesResponse {
  bubbles: BubbleInfo[];
}

export interface CurrentIndexResult {
  current_index: number;
}

export interface ActionResult {
  status?: string;
  [key: string]: unknown;
}

export interface LoadProjectResult {
  status?: string;
  page_count?: number;
  current_index?: number;
  selected_indices?: number[];
}

export interface ExportResult {
  status?: string;
  saved_path?: string;
}

export interface TranslationModelsResponse {
  provider: string;
  models: string[];
  error?: string;
}
