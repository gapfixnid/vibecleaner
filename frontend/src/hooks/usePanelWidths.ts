import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

const SIDEBAR_MIN = 220;
const SIDEBAR_MAX = 360;
const INSPECTOR_MIN = 300;
const INSPECTOR_MAX = 440;

function readStoredWidth(key: string, fallback: number, min: number, max: number): number {
  try {
    const value = Number(window.localStorage.getItem(key));
    return Number.isFinite(value) && value >= min && value <= max ? value : fallback;
  } catch {
    return fallback;
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)));
}

export function usePanelWidths() {
  const [sidebarWidth, setSidebarWidth] = useState(() => readStoredWidth("vibecleaner.sidebarWidth", 250, SIDEBAR_MIN, SIDEBAR_MAX));
  const [inspectorWidth, setInspectorWidth] = useState(() => readStoredWidth("vibecleaner.inspectorWidth", 320, INSPECTOR_MIN, INSPECTOR_MAX));
  const resizeAbortRef = useRef<AbortController | null>(null);

  useEffect(() => () => {
    resizeAbortRef.current?.abort();
    document.body.classList.remove("panel-resizing");
  }, []);

  const startResize = useCallback((
    event: ReactPointerEvent<HTMLDivElement>,
    side: "sidebar" | "inspector",
  ) => {
    event.preventDefault();
    resizeAbortRef.current?.abort();
    const controller = new AbortController();
    resizeAbortRef.current = controller;
    const startX = event.clientX;
    const startWidth = side === "sidebar" ? sidebarWidth : inspectorWidth;
    const direction = side === "sidebar" ? 1 : -1;
    const min = side === "sidebar" ? SIDEBAR_MIN : INSPECTOR_MIN;
    const max = side === "sidebar" ? SIDEBAR_MAX : INSPECTOR_MAX;
    const setter = side === "sidebar" ? setSidebarWidth : setInspectorWidth;
    document.body.classList.add("panel-resizing");

    window.addEventListener("pointermove", (moveEvent) => {
      setter(clamp(startWidth + (moveEvent.clientX - startX) * direction, min, max));
    }, { signal: controller.signal });

    const finishResize = () => {
      controller.abort();
      resizeAbortRef.current = null;
      document.body.classList.remove("panel-resizing");
    };
    window.addEventListener("pointerup", finishResize, { signal: controller.signal, once: true });
    window.addEventListener("pointercancel", finishResize, { signal: controller.signal, once: true });
  }, [inspectorWidth, sidebarWidth]);

  const adjustSidebarWidth = useCallback((delta: number) => {
    setSidebarWidth((width) => clamp(width + delta, SIDEBAR_MIN, SIDEBAR_MAX));
  }, []);
  const adjustInspectorWidth = useCallback((delta: number) => {
    setInspectorWidth((width) => clamp(width + delta, INSPECTOR_MIN, INSPECTOR_MAX));
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem("vibecleaner.sidebarWidth", String(sidebarWidth));
    } catch {
      // Local storage is optional; the in-memory width still works.
    }
  }, [sidebarWidth]);

  useEffect(() => {
    try {
      window.localStorage.setItem("vibecleaner.inspectorWidth", String(inspectorWidth));
    } catch {
      // Local storage is optional; the in-memory width still works.
    }
  }, [inspectorWidth]);

  return {
    sidebarWidth,
    inspectorWidth,
    startSidebarResize: (event: ReactPointerEvent<HTMLDivElement>) => startResize(event, "sidebar"),
    startInspectorResize: (event: ReactPointerEvent<HTMLDivElement>) => startResize(event, "inspector"),
    adjustSidebarWidth,
    adjustInspectorWidth,
  };
}
