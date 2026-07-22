import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import * as api from "../services/api";
import * as desktop from "../services/desktop";
import { mergeBackendStatus } from "../lib/backendStatus";
import type { BackendStatus } from "../types/backend";
import type { Settings } from "../types";

interface UseBackendBootstrapDeps {
  setSettings: Dispatch<SetStateAction<Settings>>;
  loadPagesFromServer: (
    selectIndex?: number,
    options?: { skipPageActivation?: boolean; throwOnError?: boolean },
  ) => Promise<void>;
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
  const hydratingGenerationRef = useRef<number | null>(null);
  const resetGenerationRef = useRef<number | null>(null);

  const loadSettingsFromServer = useCallback(async () => {
    const data = await api.getSettings();
    setSettings(data);
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
      if (hydratingGenerationRef.current === merged.generation) return;
      const previousGeneration = handledRunningGenerationRef.current;
      const generation = merged.generation;
      hydratingGenerationRef.current = generation;
      setIsBootstrapping(true);
      try {
        if (
          previousGeneration !== null
          && generation > previousGeneration
          && resetGenerationRef.current !== generation
        ) {
          await onBackendGenerationChange();
          resetGenerationRef.current = generation;
        }
        await loadSettingsFromServer();
        if (statusRef.current?.generation !== generation || statusRef.current.phase !== "running") return;
        await loadPagesFromServer(undefined, { throwOnError: true });
        if (statusRef.current?.generation !== generation || statusRef.current.phase !== "running") return;
        handledRunningGenerationRef.current = generation;
        setBackendError(null);
        setIsBootstrapping(false);
      } catch (error) {
        console.error("Failed to hydrate backend state", error);
        if (statusRef.current?.generation === generation && statusRef.current.phase === "running") {
          setBackendError({
            code: "unreachable",
            detail: error instanceof Error ? error.message : String(error),
          });
          setIsBootstrapping(false);
        }
      } finally {
        if (hydratingGenerationRef.current === generation) {
          hydratingGenerationRef.current = null;
        }
      }
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
