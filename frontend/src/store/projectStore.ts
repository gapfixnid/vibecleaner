import { VanillaStore } from "./vanillaStore";
import type { ProjectDto } from "../types/project";

export interface ProjectState {
  project: ProjectDto | null;
  isDirty: boolean;
  projectPath: string | null;
}

export const projectStore = new VanillaStore<ProjectState>({
  project: null,
  isDirty: false,
  projectPath: null,
});
