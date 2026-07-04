import type { Point, Rect } from "./common";

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
  status: string;
  problems: string[];
  edited: boolean;
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
  status: string;
  problems: string[];
}

export interface AreaDragState {
  mode: "create" | "move" | "resize";
  start: Point;
  initial: Rect;
  hasMoved: boolean;
}
