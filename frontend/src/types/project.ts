import type { BubbleDto } from "./bubble";

export interface SettingsDto {
  translation_model: string;
  translation_provider: string;
  translation_api_base_url: string;
  translation_api_key: string;
  translation_api_key_configured: boolean;
  translation_timeout_seconds: number;
  translation_supports_vision: boolean;
  translation_cache_enabled: boolean;
  translation_cache_mode: string;
  translation_max_retries: number;
  translation_retry_backoff_seconds: number;
  translation_llm_temperature: number;
  translation_llm_top_p: number;
  translation_llm_max_tokens: number;
  ui_language: string;
  source_language: string;
  target_language: string;
  system_prompt: string;
  detect_model: string;
  confidence_threshold: number;
  tiling_enabled: boolean;
  ocr_engine: string;
  ocr_padding: number;
  ocr_crop_scale: number;
  line_merge_sensitivity: number;
  adaptive_binarization: boolean;
  adaptive_binarization_strength: number;
  smart_direction: boolean;
  text_direction_override: string;
  bubbles_only: boolean;
  show_detection_overlay: boolean;
  min_font_size: number;
  max_font_size: number;
  default_font_size: number;
  inpaint_engine: string;
  inpaint_mask_dilation: number;
  inpaint_use_textbox_only: boolean;
  inpaint_clip_to_bubble: boolean;
  setup_completed: boolean;
}

export interface PageDto {
  id: string;
  index: number;
  filename: string;
  file_path: string;
  width: number;
  height: number;
  status: "idle" | "processing" | "ready_for_review" | "has_warnings" | "reviewed" | "exported" | "error" | "success" | "warning";
  has_inpaint?: boolean;
  bubbles: BubbleDto[];
  problems: string[];
  bubble_count?: number;
  translated_count?: number;
}

export interface ProjectDto {
  id: string;
  name: string;
  pages: PageDto[];
  current_page_id: string | null;
  settings: SettingsDto;
}

export interface PagesDto {
  pages: Array<{
    page_id: string;
    index: number;
    file_path: string;
    filename: string;
    width: number;
    height: number;
    bubble_count: number;
    translated_count: number;
    has_inpaint: boolean;
    status: string;
    problems: string[];
  }>;
  current_index: number;
}
