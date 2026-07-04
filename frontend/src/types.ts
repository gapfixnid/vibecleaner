// Centralized shared types used across the UI and the API service layer.

export * from "./types/common";
export * from "./types/bubble";
export * from "./types/project";
export * from "./types/problem";
export * from "./types/pipeline";
export * from "./types/api";
export * from "./types/domain";

import type { SettingsDto } from "./types/project";
import type { BubbleInfo, PageInfo } from "./types/domain";

export type Settings = SettingsDto;

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
