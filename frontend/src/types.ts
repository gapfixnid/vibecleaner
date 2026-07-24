// Centralized shared types used across the UI and the API service layer.

export * from "./types/common";
export * from "./types/bubble";
export * from "./types/project";
export * from "./types/problem";
export * from "./types/pipeline";
export * from "./types/provider";
export * from "./types/api";
export * from "./types/domain";

import type { ModelStatusDto } from "./types/api";
import type { SettingsDto } from "./types/project";
import type { BubbleInfo, PageInfo } from "./types/domain";

export type Settings = SettingsDto;

export type JobState = "queued" | "running" | "cancelling" | "succeeded" | "succeeded_with_errors" | "failed" | "cancelled";

export interface JobStatus {
  job_id: string;
  kind?: string;
  page_idx?: number;
  status: JobState;
  progress?: number;
  message?: string;
  result?: unknown;
  error?: string;
  error_code?: string;
  error_stage?: string;
  error_details?: Record<string, unknown>;
  error_retryable?: boolean;
}

export interface PagesResponse {
  pages: PageInfo[];
  current_index: number;
}

export interface BubblesResponse {
  page_id: string;
  project_generation: number;
  content_revision: number;
  visual_revision: number;
  text_layer_namespace: string;
  bubbles: BubbleInfo[];
}

export interface BubbleMutationResult extends Omit<BubblesResponse, "bubbles"> {
  status: "ok";
  changed_bubbles: BubbleInfo[];
  deleted_bubble_ids: number[];
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

export type ModelStatus = ModelStatusDto;
