import type { vibeCleanerApi } from "../types/api";
import { tauriClient } from "./tauriClient";

export const api: vibeCleanerApi = tauriClient;
export { tauriClient } from "./tauriClient";
