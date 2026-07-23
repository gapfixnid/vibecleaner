import type { Rect } from "./common";
import type { BubbleProblemDto } from "./problem";

export interface TextStyleDto {
  font_family: string;
  computed_font_family?: string;
  font_size: number;
  font_mode?: "auto" | "fixed";
  requested_font_size?: number | null;
  bold: boolean;
  italic: boolean;
  color: string;
  alignment: "left" | "center" | "right";
  computed_font_size?: number;
}

export interface TextLineDto {
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  origin_x?: number;
  baseline_y?: number;
  advance_width?: number;
  ink_left?: number;
  ink_top?: number;
  ink_width?: number;
  ink_height?: number;
  runs?: TextGlyphRunDto[];
}

export interface TextGlyphRunDto {
  text: string;
  origin_x: number;
  font_family: string;
  font_pixel_size: number;
  is_rtl: boolean;
}

export interface TextLayerRefDto {
  cache_key: string;
  pixel_digest: string;
  crop_x: number;
  crop_y: number;
  width: number;
  height: number;
  mime_type: "image/png";
}

export interface BubbleRenderStatusDto {
  status: "ready" | "pending" | "fallback";
  error_code?: string | null;
}

export interface TextLayoutDto {
  lines: TextLineDto[];
  overflow: boolean;
  line_height_ratio?: number;
  area_usage?: number;
  writing_mode?: string;
  text_direction?: string;
  justification?: string;
  padding?: Record<string, number>;
  margin?: Record<string, number>;
  confidence?: number;
  reasoning?: string;
  diagnostics?: {
    selected_pass?: "mask_strict" | "mask_relaxed" | "rect" | "fixed" | "overflow_fallback";
    selected_font_size?: number;
    largest_feasible_font_size?: number;
    strict_max_font_size?: number | null;
    relaxed_max_font_size?: number | null;
    allow_char_break?: boolean;
    candidate_count?: number;
    rasterized_candidate_count?: number;
    safe_area_ratio?: number;
    outside_alpha_ratio?: number;
    resource_violation_count?: number;
  };
}

export interface BubbleDto {
  id: string;
  bubbleBox: Rect;     // overall speech bubble region
  textBox: Rect;       // original text region
  layoutBox: Rect;     // translated text placement region
  text: string;        // OCR original text
  translated: string;  // translated text
  status:
    | "idle"
    | "ok"
    | "needs_review"
    | "ocr_warning"
    | "translation_warning"
    | "layout_overflow"
    | "edited"
    | "error"
    | "success"
    | "warning";
  style: TextStyleDto;
  layout: TextLayoutDto;
  problems: BubbleProblemDto[];
  edited?: boolean;
  text_class?: string;
  text_layer?: TextLayerRefDto | null;
  render_status?: BubbleRenderStatusDto;
  stroke_color?: string;
  stroke_width?: number;
}

export interface BubblePatchDto {
  bubbleBox?: Rect;
  textBox?: Rect;
  layoutBox?: Rect;
  text?: string;
  translated?: string;
  style?: Partial<TextStyleDto>;
}
