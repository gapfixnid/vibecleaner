export type BackendPhase =
  | "starting"
  | "running"
  | "restarting"
  | "failed"
  | "stopping"
  | "stopped";

export interface BridgeErrorDto {
  code: string;
  message: string;
  retryable: boolean;
  http_status?: number;
  request_id?: string;
}

export interface BackendStatus {
  running: boolean;
  phase: BackendPhase;
  error: BridgeErrorDto | null;
  pid: number | null;
  generation: number;
}
