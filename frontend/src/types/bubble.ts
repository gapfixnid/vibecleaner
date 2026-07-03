import type { Rect } from "./common";

export interface TextStyleDto {
  font_family: string;
  font_size: number;
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
}

export interface TextLayoutDto {
  lines: TextLineDto[];
  overflow: boolean;
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
  problems: string[];
  edited?: boolean;
  text_class?: string;
}

export interface BubblePatchDto {
  bubbleBox?: Rect;
  textBox?: Rect;
  layoutBox?: Rect;
  text?: string;
  translated?: string;
  style?: Partial<TextStyleDto>;
}
