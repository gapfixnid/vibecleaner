import { useRef, useState, useEffect, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { Toolbar } from "./components/Toolbar";
import { Canvas } from "./components/Canvas";
import { Inspector } from "./components/Inspector";
import { SettingsModal } from "./components/SettingsModal";

import { CustomDialog } from "./components/CustomDialog";
import { AboutModal } from "./components/AboutModal";
import { BackendErrorScreen } from "./components/BackendErrorScreen";
import "./styles/apple_theme.css";
import * as api from "./services/api";
import * as desktop from "./services/desktop";
import type { PageInfo, Settings } from "./types";
import { useDialog } from "./hooks/useDialog";
import { useProcessingTask } from "./hooks/useProcessingTask";
import { useBubbles } from "./hooks/useBubbles";
import { usePages } from "./hooks/usePages";
import { useProject } from "./hooks/useProject";
import { useTheme } from "./hooks/useTheme";
import { useAutoTypeset } from "./hooks/useAutoTypeset";
import { usePageExport } from "./hooks/usePageExport";
import { buildPageImageUrl as buildPageImageRequestUrl } from "./lib/pageImageUrl";

const DEFAULT_SETTINGS: Settings = {
  translation_model: "",
  translation_provider: "google",
  translation_api_base_url: "",
  translation_api_key: "",
  translation_api_key_configured: false,
  translation_timeout_seconds: 90,
  translation_supports_vision: false,
  source_language: "Japanese",
  target_language: "Korean",
  system_prompt: "",
  detect_model: "",
  confidence_threshold: 0.45,
  tiling_enabled: true,
  bubbles_only: false,
  min_font_size: 6,
  max_font_size: 48,
  default_font_size: 18,
  inpaint_mask_dilation: 2,
  inpaint_use_textbox_only: true,
  inpaint_clip_to_bubble: true,
};

function App() {
  // --- Cross-cutting concerns (dialog + processing) ---
  const { dialog, showAlert, showConfirm, showUnsavedPrompt, closeDialog } = useDialog();
  const showError = useCallback(
    (title: string, message: string) => showAlert("error", title, message),
    [showAlert]
  );

  // --- Project dirty state (unsaved-changes tracking) ---
  const [isDirty, setIsDirty] = useState(false);
  const markDirty = useCallback(() => setIsDirty(true), []);
  const markClean = useCallback(() => setIsDirty(false), []);

  // Latest sidebar selection, exposed to useProject for save/restore.
  const selectionRef = useRef<number[]>([]);
  const getSelectedIndices = useCallback(() => selectionRef.current, []);

  const {
    isProcessing,
    setIsProcessing,
    isWaitingForImageReload,
    setIsWaitingForImageReload,
    waitForJob,
    runTask,
    finishImageReload,
  } = useProcessingTask(showError);

  // Shared active-page index ref, used by both pages and bubbles hooks.
  const currentIndexRef = useRef<number>(-1);
  const pagesRef = useRef<PageInfo[]>([]);

  // --- Domain hooks ---
  // Ref pattern: onPageTranslationChanged callback is set after loadPagesFromServer
  // is available (avoids circular dependency with usePages).
  const onTranslationChangedRef = useRef<(() => void) | undefined>(undefined);
  const bubblesApi = useBubbles({
    currentIndexRef,
    pagesRef,
    runTask,
    waitForJob,
    showError,
    markDirty,
    onPageTranslationChanged: () => onTranslationChangedRef.current?.(),
  });
  const pagesApi = usePages({
    currentIndexRef,
    runTask,
    showError,
    showConfirm,
    onPageActivated: bubblesApi.handlePageActivated,
    onPagesCleared: bubblesApi.clearBubbles,
    markDirty,
  });
  const projectApi = useProject({
    runTask,
    showAlert,
    loadPagesFromServer: pagesApi.loadPagesFromServer,
    markDirty,
    markClean,
    getSelectedIndices,
  });

  const { pages, currentIndex, pageVersions, bumpPageVersion, resetPageVersions, loadPagesFromServer } = pagesApi;

  useEffect(() => {
    pagesRef.current = pages;
  }, [pages]);

  // Wire up the translation-changed callback once loadPagesFromServer is ready.
  useEffect(() => {
    onTranslationChangedRef.current = () => loadPagesFromServer();
  }, [loadPagesFromServer]);

  const { bubbles, selectedBubbleId, setSelectedBubbleId, syncBubblesToBackend } =
    bubblesApi;

  // --- Local UI state ---
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [selectedPageIds, setSelectedPageIds] = useState<number[]>([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isAboutOpen, setIsAboutOpen] = useState(false);
  const { theme, setTheme, themes } = useTheme();
  const [backendError, setBackendError] = useState<string | null>(null);
  const [isRetryingBackend, setIsRetryingBackend] = useState(false);

  useEffect(() => {
    selectionRef.current = selectedPageIds;
  }, [selectedPageIds]);

  const { handleTranslate, handleTranslatePages } = useAutoTypeset({
    pages,
    selectedPageIds,
    currentIndexRef,
    runTask,
    waitForJob,
    syncBubblesToBackend,
    setIsWaitingForImageReload,
    setIsProcessing,
    bumpPageVersion,
    loadPagesFromServer,
    setSelectedPageIds,
    selectPage: pagesApi.handleSelectPage,
  });

  const { handleExportPages } = usePageExport({
    pages,
    runTask,
    waitForJob,
    syncBubblesToBackend,
    bumpPageVersion,
    loadPagesFromServer,
    showAlert,
  });

  const loadSettingsFromServer = useCallback(async () => {
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (e) {
      console.error("Failed to load settings from server", e);
    }
  }, []);

  // Initial bootstrap: resolve port, check backend health, then load data.
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
          // Command unavailable (e.g. running outside Tauri) — assume the
          // backend is managed externally and proceed.
          console.log("getBackendStatus unavailable; assuming backend managed externally", e);
        }
      } catch (e) {
        console.log("Not running inside Tauri or failed to get port. Using fallback port 8000.", e);
      }
      if (backendOk) {
        // The backend process may be up but not yet accepting HTTP connections.
        // Probe with a few retries; surface a recoverable error if unreachable.
        let reachable = false;
        for (let attempt = 0; attempt < 8; attempt++) {
          try {
            await api.getSettings();
            reachable = true;
            break;
          } catch {
            await new Promise((r) => setTimeout(r, 500));
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // Keyboard shortcuts (Ctrl+,: settings)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = document.activeElement?.tagName.toLowerCase();
      if (activeTag === "input" || activeTag === "textarea" || activeTag === "select") {
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === ",") {
        e.preventDefault();
        setIsSettingsOpen(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Restrict default context menu to allowed areas
  useEffect(() => {
    const handleGlobalContextMenu = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;
      const isAllowed =
        target.closest(".canvas-container") ||
        target.closest(".page-item") ||
        target.closest(".sidebar-context-menu") ||
        target.tagName.toLowerCase() === "input" ||
        target.tagName.toLowerCase() === "textarea";
      if (!isAllowed) e.preventDefault();
    };
    window.addEventListener("contextmenu", handleGlobalContextMenu);
    return () => window.removeEventListener("contextmenu", handleGlobalContextMenu);
  }, []);

  // --- Selection state management ---

  // Anchor for Shift-range selection — always tracks the "base" page index.
  const rangeAnchorRef = useRef<number | null>(null);

  // Keep in sync with currentIndex so Shift+click works right after page load
  // (when no user click has occurred yet).
  useEffect(() => {
    rangeAnchorRef.current = currentIndex;
  }, [currentIndex]);

  // Selection handlers (owner of selection logic lives in App, not Sidebar).
  const handlePageSelection = useCallback(
    (e: React.MouseEvent, pageIdx: number) => {
      if (e.ctrlKey || e.metaKey) {
        // Ctrl/Cmd click: toggle selection (always keep at least 1 selected)
        const exists = selectedPageIds.includes(pageIdx);
        let nextIds: number[];
        if (exists) {
          if (selectedPageIds.length === 1) return; // 마지막 1개는 deselect 불가
          nextIds = selectedPageIds.filter((id) => id !== pageIdx);
        } else {
          nextIds = [...selectedPageIds, pageIdx];
        }
        setSelectedPageIds(nextIds);
        if (nextIds.length === 1) pagesApi.handleSelectPage(nextIds[0]);
      } else if (e.shiftKey && rangeAnchorRef.current !== null) {
        // Shift click: range selection
        const from = Math.min(rangeAnchorRef.current, pageIdx);
        const to = Math.max(rangeAnchorRef.current, pageIdx);
        const range: number[] = [];
        for (let i = from; i <= to; i++) {
          range.push(i);
        }
        setSelectedPageIds(range);
        if (range.length === 1) pagesApi.handleSelectPage(range[0]);
      } else {
        // Normal click: single selection
        pagesApi.handleSelectPage(pageIdx);
        setSelectedPageIds([pageIdx]);
      }
      rangeAnchorRef.current = pageIdx;
    },
    [pagesApi, selectedPageIds]
  );

  const handleSelectAllPages = useCallback(() => {
    const allIds = pages.map((p) => p.index);
    setSelectedPageIds(allIds);
  }, [pages]);

  // Ctrl+A select all (when focus is in Sidebar).
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        const inSidebar = document.activeElement?.closest?.(".sidebar-container");
        if (inSidebar) {
          e.preventDefault();
          handleSelectAllPages();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSelectAllPages]);

  // Clear bubble selection when multiple pages are selected (future-proofing).
  useEffect(() => {
    if (selectedPageIds.length > 1) {
      setSelectedBubbleId(null);
    }
  }, [selectedPageIds.length, setSelectedBubbleId]);

  // --- Project lifecycle with unsaved-changes guard ---

  // Run `proceed` immediately when clean; otherwise prompt Save / Don't Save / Cancel.
  const guardUnsaved = useCallback(
    (proceed: () => void) => {
      if (!isDirty) {
        proceed();
        return;
      }
      showUnsavedPrompt(
        "Unsaved Changes",
        "You have unsaved changes. Do you want to save them before continuing?",
        async () => {
          const saved = await projectApi.handleSaveProject();
          if (saved) proceed();
        },
        () => proceed()
      );
    },
    [isDirty, showUnsavedPrompt, projectApi]
  );

  // Window-close listener is registered once; refs feed it the latest values.
  const isDirtyRef = useRef(false);
  const closingRef = useRef(false);
  const guardUnsavedRef = useRef(guardUnsaved);
  useEffect(() => {
    isDirtyRef.current = isDirty;
  }, [isDirty]);
  useEffect(() => {
    guardUnsavedRef.current = guardUnsaved;
  }, [guardUnsaved]);

  // Guard window close (traffic-light close button → close(), Alt+F4, taskbar)
  // against unsaved changes. CRITICAL: only ever preventDefault when the project
  // is dirty AND a close isn't already in progress — so a clean project (and the
  // app at startup) always closes normally and can never get trapped.
  useEffect(() => {
    let unlisten: () => void = () => {};
    let active = true;
    desktop
      .onWindowCloseRequested((event) => {
        console.log("[close-guard] close requested. dirty=", isDirtyRef.current, "closing=", closingRef.current);
        if (closingRef.current || !isDirtyRef.current) {
          return; // allow the close to proceed
        }
        event.preventDefault();
        try {
          guardUnsavedRef.current(() => {
            closingRef.current = true;
            desktop.destroyWindow();
          });
        } catch (e) {
          // Fail-safe: never trap the user if the prompt logic throws.
          console.error("[close-guard] prompt failed; forcing close", e);
          closingRef.current = true;
          desktop.destroyWindow();
        }
      })
      .then((fn) => {
        if (active) unlisten = fn;
        else fn();
      });
    return () => {
      active = false;
      unlisten();
    };
  }, []);

  const handleNewProject = useCallback(() => {
    guardUnsaved(async () => {
      const ok = await projectApi.handleNewProject();
      if (ok) {
        resetPageVersions();
        setSelectedPageIds([]);
        setSelectedBubbleId(null);
      }
    });
  }, [guardUnsaved, projectApi, resetPageVersions, setSelectedBubbleId]);

  const handleOpenProject = useCallback(() => {
    guardUnsaved(async () => {
      const restoredSelection = await projectApi.handleLoadProject();
      if (restoredSelection) {
        resetPageVersions();
        setSelectedPageIds(restoredSelection);
        setSelectedBubbleId(null);
      }
    });
  }, [guardUnsaved, projectApi, resetPageVersions, setSelectedBubbleId]);

  // Resolve the target page set for a context-menu action: the whole
  // multi-selection if the right-clicked page is part of it, else just that page.
  const resolveContextTargets = useCallback(
    (idx: number) =>
      selectedPageIds.length > 1 && selectedPageIds.includes(idx) ? [...selectedPageIds] : [idx],
    [selectedPageIds]
  );

  const handleContextTranslate = useCallback(
    (idx: number) => {
      const ids = resolveContextTargets(idx);
      handleTranslatePages(ids);
    },
    [resolveContextTargets, handleTranslatePages]
  );

  const handleContextSaveImages = useCallback(
    (idx: number) => {
      handleExportPages(resolveContextTargets(idx));
    },
    [resolveContextTargets, handleExportPages]
  );

  const handleRenamePage = useCallback(
    async (idx: number, name: string) => {
      const pageId = pages[idx]?.page_id;
      if (!pageId) return;
      await runTask(
        "Renaming page...",
        async () => {
          await api.renamePage(pageId, name);
          await loadPagesFromServer(currentIndexRef.current, { skipPageActivation: true });
          markDirty();
        },
        { errorTitle: "Rename Failed" }
      );
    },
    [pages, runTask, loadPagesFromServer, markDirty]
  );

  const handleSaveSettings = useCallback(async (updated: Settings) => {
    try {
      const saved = await api.updateSettings(updated);
      setSettings(saved);
    } catch (e) {
      console.error("Failed to auto-save settings", e);
    }
  }, []);

  // --- Derived view data ---
  const activePage: PageInfo | undefined = pages[currentIndex];
  const activeBubble = bubbles.find((b) => b.id === selectedBubbleId) || null;
  const currentBackendUrl = api.getBackendUrl();

  // Selection-derived values
  const isMultiPageSelection = selectedPageIds.length > 1;

  const buildPageImageUrl = useCallback(
    (page: PageInfo, preview = true) => {
      return buildPageImageRequestUrl({
        backendUrl: currentBackendUrl,
        page,
        pageVersion: pageVersions[page.index] || 0,
        preview,
      });
    },
    [currentBackendUrl, pageVersions]
  );

  // Prefetch adjacent pages so navigation hits the browser cache.
  useEffect(() => {
    if (currentIndex < 0 || pages.length === 0) return;
    const adjacentPages = [pages[currentIndex + 1], pages[currentIndex - 1]].filter(
      (page): page is PageInfo => Boolean(page)
    );
    const prefetchers = adjacentPages.map((page) => {
      const img = new Image();
      img.decoding = "async";
      img.src = buildPageImageUrl(page);
      return img;
    });
    return () => {
      prefetchers.forEach((img) => {
        img.src = "";
      });
    };
  }, [buildPageImageUrl, currentIndex, pages]);

  return (
    <div className="app-container">
      <Toolbar
        onNewProject={handleNewProject}
        onOpenProject={handleOpenProject}
        onSaveProject={projectApi.handleSaveProject}
        onPreferences={() => setIsSettingsOpen(true)}
        onAbout={() => setIsAboutOpen(true)}
        isDirty={isDirty}
      />

      <div className="main-workspace">
        <Sidebar
          pages={pages}
          currentIndex={currentIndex}
          selectedPageIds={selectedPageIds}
          pageVersions={pageVersions}
          onSelectPage={pagesApi.handleSelectPage}
          onPageClick={handlePageSelection}
          onSelectAllPages={handleSelectAllPages}
          onDuplicatePage={(idx) => pagesApi.handleDuplicatePages(resolveContextTargets(idx))}
          onDeletePage={(idx) => {
            // If the right-clicked page is part of the multi-selection, delete all selected.
            const isSelected = selectedPageIds.length > 1 && selectedPageIds.includes(idx);
            pagesApi.handleDeletePages(isSelected ? selectedPageIds : [idx]);
          }}
          onReorderPages={pagesApi.handleReorderPages}
          onImportImages={async () => {
            const result = await projectApi.handleOpenFiles();
            if (!result) return;
            const { beforeCount, afterCount, addedCount } = result;
            if (beforeCount === 0 && addedCount > 0) {
              // 빈 프로젝트 + N장 추가 → 첫 페이지 선택
              pagesApi.handleSelectPage(0);
              setSelectedPageIds([0]);
            } else if (addedCount === 1) {
              // 1장 추가 → 새 페이지 선택
              const newIndex = afterCount - 1;
              pagesApi.handleSelectPage(newIndex);
              setSelectedPageIds([newIndex]);
            }
            // else: 기존 프로젝트 + N장 → 현재 선택 유지
          }}
          onExportSelectedImages={() => handleExportPages(selectedPageIds)}
          onRenamePage={handleRenamePage}
          onTranslatePages={handleContextTranslate}
          onSaveImages={handleContextSaveImages}
          backendUrl={currentBackendUrl}
        />

        <Canvas
          imageUrl={currentIndex >= 0 && activePage ? buildPageImageUrl(activePage) : ""}
          fullResImageUrl={currentIndex >= 0 && activePage ? buildPageImageUrl(activePage, false) : ""}
          imageWidth={activePage?.width}
          imageHeight={activePage?.height}
          pageIndex={currentIndex}
          bubbles={bubbles}
          selectedBubbleId={selectedBubbleId}
          onSelectBubble={setSelectedBubbleId}
          onPreviewBubbles={bubblesApi.handlePreviewBubbles}
          onUpdateBubbles={bubblesApi.handleUpdateBubbles}
          onTranslate={handleTranslate}
          isProcessing={isProcessing}
          onDeleteBubble={bubblesApi.handleDeleteBubble}
          onImageLoaded={finishImageReload}
          isMultiPageSelection={isMultiPageSelection}
          selectedPageCount={selectedPageIds.length}
          isWaitingForImageReload={isWaitingForImageReload}
        />

        <Inspector
          selectedBubble={activeBubble}
          settings={settings}
          onUpdateBubble={bubblesApi.handleUpdateBubble}
          onReOcrBubble={bubblesApi.handleReOcrBubble}
          onReTranslateBubble={bubblesApi.handleReTranslateBubble}
          isProcessing={isProcessing}
          isMultiPageSelection={isMultiPageSelection}
        />
      </div>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onSave={handleSaveSettings}
        backendUrl={currentBackendUrl}
        theme={theme}
        setTheme={setTheme}
        themes={themes}
      />

      <CustomDialog options={dialog} onClose={closeDialog} />

      <AboutModal isOpen={isAboutOpen} onClose={() => setIsAboutOpen(false)} />

      {backendError && (
        <BackendErrorScreen
          error={backendError}
          isRetrying={isRetryingBackend}
          onRetry={handleRetryBackend}
        />
      )}

      <style>{`
        .main-workspace {
          display: flex;
          flex: 1;
          height: calc(100vh - var(--toolbar-height));
          overflow: hidden;
        }
      `}</style>
    </div>
  );
}

export default App;
