import { VanillaStore } from "./vanillaStore";
import type { SettingsDto } from "../types/project";

export interface SettingsState {
  settings: SettingsDto | null;
}

export const settingsStore = new VanillaStore<SettingsState>({
  settings: null,
});
