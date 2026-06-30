import type { BubbleDto } from "./bubble";

export interface SettingsDto {
  translation_model: string;
  translation_provider: string;
  translation_api_base_url: string;
  translation_api_key: string;
  translation_api_key_configured: boolean;
  translation_timeout_seconds: number;
  translation_supports_vision: boolean;
  source_language: string;
  target_language: string;
  system_prompt: string;
  detect_model: string;
  confidence_threshold: number;
  tiling_enabled: boolean;
  bubbles_only: boolean;
  min_font_size: number;
  max_font_size: number;
  default_font_size: number;
  inpaint_mask_dilation: number;
  inpaint_use_textbox_only: boolean;
  inpaint_clip_to_bubble: boolean;
}

export interface PageDto {
  id: string;
  index: number;
  filename: string;
  file_path: string;
  width: number;
  height: number;
  status: "idle" | "processing" | "success" | "warning" | "error";
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
