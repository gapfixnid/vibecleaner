import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from "react";
import * as api from "../services/api";
import * as desktop from "../services/desktop";
import type { Settings } from "../types";

interface UseBackendBootstrapDeps {
  setSettings: Dispatch<SetStateAction<Settings>>;
  loadPagesFromServer: () => Promise<void>;
}

export function useBackendBootstrap({ setSettings, loadPagesFromServer }: UseBackendBootstrapDeps) {
  const [backendError, setBackendError] = useState<string | null>(null);
  const [isRetryingBackend, setIsRetryingBackend] = useState(false);

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
            setBackendError(status.error || "백엔드 서버를 시작하지 못했습니다.");
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
          setBackendError("백엔드 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
          return;
        }
        loadSettingsFromServer();
        loadPagesFromServer();
      }
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
        setBackendError(status.error || "백엔드 서버를 시작하지 못했습니다.");
      }
    } catch (e) {
      console.error("retry_backend invocation failed", e);
      setBackendError("백엔드 재시작 명령을 호출하지 못했습니다.");
    } finally {
      setIsRetryingBackend(false);
    }
  }, [loadSettingsFromServer, loadPagesFromServer]);

  return {
    backendError,
    isRetryingBackend,
    handleRetryBackend,
  };
}
