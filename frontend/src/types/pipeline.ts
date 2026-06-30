export type PipelineStage =
  | "detect"
  | "ocr"
  | "reading_order"
  | "bubble_analysis"
  | "inpaint"
  | "translate"
  | "typeset"
  | "preview_render"
  | "completed";

export interface PipelineProgressDto {
  page_id: string;
  stage: PipelineStage;
  progress: number; // 0-100
  message: string;
  timestamp: string;
}

export interface PipelineTargetDto {
  project_id: string;
  page_ids: string[];
}
