import { invoke } from "@tauri-apps/api/core";

export interface BackendStatus {
  running: boolean;
  error: string | null;
  port: number;
}

export const getApiPort = async (): Promise<number> => {
  return await invoke<number>("get_api_port");
};

export const getBackendStatus = async (): Promise<BackendStatus> => {
  return await invoke<BackendStatus>("get_backend_status");
};

export const retryBackend = async (): Promise<BackendStatus> => {
  return await invoke<BackendStatus>("retry_backend");
};

export const selectDirectory = async (): Promise<string | null> => {
  return await invoke<string | null>("select_directory");
};

export const selectFile = async (options: {
  title: string;
  filters?: [string, string[]][];
}): Promise<string | null> => {
  return await invoke<string | null>("select_file", options);
};

export const selectMultipleFiles = async (options: {
  title: string;
  filters?: [string, string[]][];
}): Promise<string[] | null> => {
  return await invoke<string[] | null>("select_multiple_files", options);
};

export const saveFile = async (options: {
  title: string;
  defaultExt: string;
  filters?: [string, string[]][];
}): Promise<string | null> => {
  return await invoke<string | null>("save_file", options);
};

export const closeWindow = async (): Promise<void> => {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().close();
  } catch (e) {
    console.error("Tauri closeWindow failed:", e);
  }
};

/** Subscribe to the window close-requested event (titlebar/traffic-light close
 *  via close(), Alt+F4, taskbar close). The handler receives the event and may
 *  call `event.preventDefault()` to block the close. Returns an unlisten fn.
 *  No-ops gracefully outside Tauri. */
export const onWindowCloseRequested = async (
  handler: (event: { preventDefault: () => void }) => void
): Promise<() => void> => {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    const unlisten = await getCurrentWindow().onCloseRequested((event) => {
      handler(event);
    });
    console.log("[close-guard] onCloseRequested listener registered");
    return unlisten;
  } catch (e) {
    console.error("Tauri onCloseRequested unavailable:", e);
    return () => {};
  }
};

export const minimizeWindow = async (): Promise<void> => {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().minimize();
  } catch (e) {
    console.error("Tauri minimizeWindow failed:", e);
  }
};

export const toggleMaximizeWindow = async (): Promise<void> => {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().toggleMaximize();
  } catch (e) {
    console.error("Tauri toggleMaximizeWindow failed:", e);
  }
};
