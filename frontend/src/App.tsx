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
import type { PageInfo, Settings } from "./types";
import { useDialog } from "./hooks/useDialog";
import { useProcessingTask } from "./hooks/useProcessingTask";
import { useBubbles } from "./hooks/useBubbles";
import { usePages } from "./hooks/usePages";
import { useProject } from "./hooks/useProject";
import { useTheme } from "./hooks/useTheme";
import { useAutoTypeset } from "./hooks/useAutoTypeset";
import { usePageExport } from "./hooks/usePageExport";
import { usePageSelection } from "./hooks/usePageSelection";
import { useBackendBootstrap } from "./hooks/useBackendBootstrap";
import { useWindowCloseGuard } from "./hooks/useWindowCloseGuard";
import { useAppChrome } from "./hooks/useAppChrome";
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
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isAboutOpen, setIsAboutOpen] = useState(false);
  const { theme, setTheme, themes } = useTheme();

  const clearBubbleSelection = useCallback(() => setSelectedBubbleId(null), [setSelectedBubbleId]);
  const {
    selectedPageIds,
    setSelectedPageIds,
    handlePageSelection,
    handleSelectAllPages,
    resolveContextTargets,
  } = usePageSelection({
    pages,
    currentIndex,
    selectionRef,
    selectPage: pagesApi.handleSelectPage,
    clearBubbleSelection,
  });

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

  const { backendError, isRetryingBackend, handleRetryBackend } = useBackendBootstrap({
    setSettings,
    loadPagesFromServer,
  });

  useAppChrome({ openSettings: () => setIsSettingsOpen(true) });

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

  useWindowCloseGuard(isDirty, guardUnsaved);

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
