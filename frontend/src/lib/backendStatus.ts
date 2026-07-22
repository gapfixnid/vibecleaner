import type { BackendPhase, BackendStatus } from "../types/backend";

const SAME_GENERATION_TRANSITIONS: Record<BackendPhase, ReadonlySet<BackendPhase>> = {
  restarting: new Set(["restarting", "starting", "failed", "stopping"]),
  starting: new Set(["starting", "running", "failed", "stopping"]),
  running: new Set(["running", "failed", "stopping"]),
  failed: new Set(["failed", "stopping"]),
  stopping: new Set(["stopping", "stopped"]),
  stopped: new Set(["stopped"]),
};

export function mergeBackendStatus(
  current: BackendStatus | null,
  incoming: BackendStatus,
): BackendStatus {
  if (!current || incoming.generation > current.generation) return incoming;
  if (incoming.generation < current.generation) return current;
  return SAME_GENERATION_TRANSITIONS[current.phase].has(incoming.phase) ? incoming : current;
}
