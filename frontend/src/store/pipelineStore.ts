import { VanillaStore } from "./vanillaStore";
import type { PipelineProgressDto } from "../types/pipeline";

export interface PipelineState {
  activePipelines: Record<string, PipelineProgressDto>;
  completedPages: Record<string, number>;
}

export const pipelineStore = new VanillaStore<PipelineState>({
  activePipelines: {},
  completedPages: {},
});
