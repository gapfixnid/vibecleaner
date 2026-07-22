import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import * as api from "../services/api";
import * as desktop from "../services/desktop";
import { mergeBackendStatus } from "../lib/backendStatus";
import type { BackendStatus } from "../types/backend";
import type { Settings } from "../types";

interface UseBackendBootstrapDeps {
  setSettings: Dispatch<SetStateAction<Settings>>;
  loadPagesFromServer: () => Promise<void>;
  onBackendGenerationChange: () => void | Promise<void>;
}

export interface BackendErrorInfo {
  code: "start_failed" | "unreachable" | "restart_failed";
  detail: string | null;
}

export function useBackendBootstrap({
  setSettings,
  loadPagesFromServer,
  onBackendGenerationChange,
}: UseBackendBootstrapDeps) {
  const [backendError, setBackendError] = useState<BackendErrorInfo | null>(null);
  const [isRetryingBackend, setIsRetryingBackend] = useState(false);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const statusRef = useRef<BackendStatus | null>(null);
  const handledRunningGenerationRef = useRef<number | null>(null);

  const loadSettingsFromServer = useCallback(async () => {
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (error) {
      console.error("Failed to load settings from server", error);
    }
  }, [setSettings]);

  const applyStatus = useCallback(async (incoming: BackendStatus) => {
    const current = statusRef.current;
    const merged = mergeBackendStatus(current, incoming);
    if (current === merged && current !== incoming) return;
    statusRef.current = merged;

    if (merged.phase === "starting" || merged.phase === "restarting") {
      setIsBootstrapping(true);
      return;
    }
    if (merged.phase === "running") {
      if (handledRunningGenerationRef.current === merged.generation) return;
      const previousGeneration = handledRunningGenerationRef.current;
      handledRunningGenerationRef.current = merged.generation;
      if (previousGeneration !== null && merged.generation > previousGeneration) {
        await onBackendGenerationChange();
      }
      setBackendError(null);
      await loadSettingsFromServer();
      await loadPagesFromServer();
      setIsBootstrapping(false);
      return;
    }
    if (merged.phase === "failed") {
      setBackendError({ code: "start_failed", detail: merged.error?.message ?? null });
      setIsBootstrapping(false);
      return;
    }
    if (merged.phase === "stopped" && handledRunningGenerationRef.current !== null) {
      setBackendError({ code: "unreachable", detail: merged.error?.message ?? null });
      setIsBootstrapping(false);
    }
  }, [loadPagesFromServer, loadSettingsFromServer, onBackendGenerationChange]);

  useEffect(() => {
    let disposed = false;
    let unlisten = () => {};

    const initialize = async () => {
      try {
        unlisten = await desktop.onBackendStatusChanged((status) => {
          if (!disposed) void applyStatus(status);
        });
        const status = await desktop.getBackendStatus();
        if (!disposed) await applyStatus(status);
      } catch (error) {
        if (!disposed) {
          setBackendError({
            code: "start_failed",
            detail: error instanceof Error ? error.message : String(error),
          });
          setIsBootstrapping(false);
        }
      }
    };
    void initialize();
    return () => {
      disposed = true;
      unlisten();
    };
  }, [applyStatus]);

  const handleRetryBackend = useCallback(async () => {
    setIsRetryingBackend(true);
    try {
      const status = await desktop.retryBackend();
      await applyStatus(status);
    } catch (error) {
      console.error("retry_backend invocation failed", error);
      setBackendError({
        code: "restart_failed",
        detail: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setIsRetryingBackend(false);
    }
  }, [applyStatus]);

  return {
    backendError,
    isRetryingBackend,
    isBootstrapping,
    handleRetryBackend,
  };
}
