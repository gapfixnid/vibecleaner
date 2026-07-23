export type ProblemCode =
  | "OCR_EMPTY"
  | "OCR_LOW_CONFIDENCE"
  | "TRANSLATE_FAILED"
  | "TEXT_OVERFLOW"
  | "BUBBLE_ANALYSIS_FALLBACK"
  | "INPAINT_LOW_QUALITY"
  | "MODEL_MISSING"
  | "WORKER_CRASH"
  | "EXPORT_FAILED";

export interface ProblemDto {
  code: ProblemCode;
  message: string;
  page_id?: string;
  bubble_id?: string;
  severity: "info" | "warning" | "error";
}

export type BubbleProblemCode =
  | "BUBBLE_ASSOCIATION_UNCERTAIN"
  | "MASK_UNCERTAIN"
  | "OCR_UNCERTAIN"
  | "TRANSLATION_EXPANDED"
  | "TEXT_OVERFLOW"
  | "LEGACY_REVIEW_NOTE";

export interface BubbleProblemDto {
  code: BubbleProblemCode;
  detail?: string | null;
}
