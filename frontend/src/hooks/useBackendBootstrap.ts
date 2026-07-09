import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from "react";
import * as api from "../services/api";
import * as desktop from "../services/desktop";
import type { Settings } from "../types";

interface UseBackendBootstrapDeps {
  setSettings: Dispatch<SetStateAction<Settings>>;
  loadPagesFromServer: () => Promise<void>;
}

/** Machine-readable backend failure; BackendErrorScreen maps codes to
 *  translated copy (the backend's ui_language is unavailable here). */
export interface BackendErrorInfo {
  code: "start_failed" | "unreachable" | "restart_failed";
  /** Raw error detail from the backend/Tauri layer, if any. */
  detail: string | null;
}

export function useBackendBootstrap({ setSettings, loadPagesFromServer }: UseBackendBootstrapDeps) {
  const [backendError, setBackendError] = useState<BackendErrorInfo | null>(null);
  const [isRetryingBackend, setIsRetryingBackend] = useState(false);
  /** True until the backend is reachable (or declared failed) — drives boot skeletons. */
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  const loadSettingsFromServer = useCallback(async () => {
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (e) {
      console.error("Failed to load settings from server", e);
    }
  }, [setSettings]);

  useEffect(() => {
    const initTauri = async () => {
      let backendOk = true;
      try {
        const port = await desktop.getApiPort();
        api.setBackendUrl(`http://127.0.0.1:${port}`);
        console.log("Resolved dynamic API port from Tauri:", port);
        try {
          const status = await desktop.getBackendStatus();
          if (!status.running) {
            backendOk = false;
            setBackendError({ code: "start_failed", detail: status.error || null });
          }
        } catch (e) {
          console.log("getBackendStatus unavailable; assuming backend managed externally", e);
        }
      } catch (e) {
        console.log("Not running inside Tauri or failed to get port. Using fallback port 8000.", e);
      }
      if (backendOk) {
        let reachable = false;
        for (let attempt = 0; attempt < 8; attempt++) {
          try {
            await api.getSettings();
            reachable = true;
            break;
          } catch {
            await new Promise((resolve) => setTimeout(resolve, 500));
          }
        }
        if (!reachable) {
          setBackendError({ code: "unreachable", detail: null });
          setIsBootstrapping(false);
          return;
        }
        loadSettingsFromServer();
        await loadPagesFromServer();
      }
      setIsBootstrapping(false);
    };
    initTauri();
  }, [loadPagesFromServer, loadSettingsFromServer]);

  const handleRetryBackend = useCallback(async () => {
    setIsRetryingBackend(true);
    try {
      const status = await desktop.retryBackend();
      if (status.running) {
        setBackendError(null);
        loadSettingsFromServer();
        await loadPagesFromServer();
      } else {
        setBackendError({ code: "start_failed", detail: status.error || null });
      }
    } catch (e) {
      console.error("retry_backend invocation failed", e);
      setBackendError({ code: "restart_failed", detail: e instanceof Error ? e.message : null });
    } finally {
      setIsRetryingBackend(false);
    }
  }, [loadSettingsFromServer, loadPagesFromServer]);

  return {
    backendError,
    isRetryingBackend,
    isBootstrapping,
    handleRetryBackend,
  };
}
