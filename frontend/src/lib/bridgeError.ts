export interface NormalizedBridgeError {
  code: string;
  message: string;
  retryable?: boolean;
  details: unknown;
}

export function normalizeBridgeError(error: unknown): NormalizedBridgeError {
  let normalized = error;
  if (typeof error === "string" && error.trimStart().startsWith("{")) {
    try {
      normalized = JSON.parse(error);
    } catch {
      // A legacy text error may happen to begin with `{`.
    }
  }
  const details = typeof normalized === "object" && normalized !== null
    ? normalized as Record<string, unknown>
    : null;
  return {
    code: typeof details?.code === "string" ? details.code : "TAURI_ERROR",
    message: typeof details?.message === "string" ? details.message : String(error),
    retryable: typeof details?.retryable === "boolean" ? details.retryable : undefined,
    details: normalized,
  };
}
