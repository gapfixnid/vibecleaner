import type { Point, Rect } from "./common";

export interface LineLayout {
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
  runs?: import("./bubble").TextGlyphRunDto[];
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
  computed_font_family: string;
  font_size: number;
  font_mode: "auto" | "fixed";
  requested_font_size: number | null;
  computed_font_size: number;
  bold: boolean;
  italic: boolean;
  color: string;
  alignment: string;
  text_class: string;
  status: string;
  problems: string[];
  edited: boolean;
  layout_overflow: boolean;
  line_height_ratio: number;
  layout_area_usage: number;
  writing_mode: string;
  text_direction: string;
  justification: string;
  layout_padding: Record<string, number>;
  layout_margin: Record<string, number>;
  layout_confidence: number;
  detection_confidence?: number;
  layout_reasoning: string;
  lines: LineLayout[];
  text_box?: { x: number; y: number; width: number; height: number } | null;
  text_layer: import("./bubble").TextLayerRefDto | null;
  render_status: import("./bubble").BubbleRenderStatusDto;
  stroke_color: string;
  stroke_width: number;
  text_layer_namespace: string;
  page_width: number;
  page_height: number;
  page_id: string;
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
  computed_font_family?: string;
  font_size: number;
  font_mode: "auto" | "fixed";
  requested_font_size: number | null;
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
  status: string;
  problems: string[];
}

export interface AreaDragState {
  mode: "create" | "move" | "resize";
  start: Point;
  initial: Rect;
  hasMoved: boolean;
}
