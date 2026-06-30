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
