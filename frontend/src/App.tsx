import { useState, useCallback, useMemo } from "react";
import { Sidebar } from "./components/Sidebar";
import { Toolbar } from "./components/Toolbar";
import { Canvas } from "./components/Canvas";
import { Inspector } from "./components/Inspector";
import { SettingsModal } from "./components/SettingsModal";
import { InitialSetupModal } from "./components/InitialSetupModal";

import { CustomDialog } from "./components/CustomDialog";
import { AboutModal } from "./components/AboutModal";
import { BackendErrorScreen } from "./components/BackendErrorScreen";
import "./styles/apple_theme.css";
import { useDialog } from "./hooks/useDialog";
import { useProcessingTask } from "./hooks/useProcessingTask";
import { useProject } from "./hooks/useProject";
import { useTheme } from "./hooks/useTheme";
import { usePageTranslation } from "./hooks/usePageTranslation";
import { usePageExport } from "./hooks/usePageExport";
import { useBackendBootstrap } from "./hooks/useBackendBootstrap";
import { useWindowCloseGuard } from "./hooks/useWindowCloseGuard";
import { useAppChrome } from "./hooks/useAppChrome";
import { useProjectActions } from "./hooks/useProjectActions";
import { useAppSettings } from "./hooks/useAppSettings";
import { useWorkspacePages } from "./hooks/useWorkspacePages";
import { createTranslator } from "./i18n";

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
  const { settings, setSettings, handleSaveSettings } = useAppSettings();
  const t = useMemo(() => createTranslator(settings.ui_language), [settings.ui_language]);

  const {
    isProcessing,
    isWaitingForImageReload,
    setIsWaitingForImageReload,
    waitForJob,
    runTask,
    finishImageReload,
  } = useProcessingTask(showError, t);

  // --- Domain hooks ---
  const workspacePages = useWorkspacePages({
    runTask,
    waitForJob,
    showError,
    showConfirm,
    markDirty,
    t,
  });
  const {
    activeBubble,
    activePage,
    backendUrl: currentBackendUrl,
    bubblesApi,
    buildPageImageUrl,
    currentIndex,
    currentIndexRef,
    getSelectedIndices,
    isMultiPageSelection,
    loadPagesFromServer,
    pages,
    pagesApi,
    selectionApi,
  } = workspacePages;
  const projectApi = useProject({
    runTask,
    showAlert,
    loadPagesFromServer: pagesApi.loadPagesFromServer,
    markDirty,
    markClean,
    getSelectedIndices,
    t,
  });

  const { bubbles, selectedBubbleId, setSelectedBubbleId, syncBubblesToBackend } =
    bubblesApi;

  // --- Local UI state ---
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isAboutOpen, setIsAboutOpen] = useState(false);
  const { theme, setTheme, themes } = useTheme();

  const {
    selectedPageIds,
    setSelectedPageIds,
    handlePageSelection,
    handleSelectAllPages,
    resolveContextTargets,
  } = selectionApi;

  const { handleTranslate, handleTranslatePages } = usePageTranslation({
    pages,
    selectedPageIds,
    currentIndexRef,
    runTask,
    waitForJob,
    syncBubblesToBackend,
    setIsWaitingForImageReload,
    bumpPageVersion: pagesApi.bumpPageVersion,
    loadPagesFromServer,
    fetchBubblesForPage: bubblesApi.fetchBubblesForPage,
    setSelectedPageIds,
    selectPage: pagesApi.handleSelectPage,
    t,
  });

  const { handleExportPages } = usePageExport({
    pages,
    runTask,
    waitForJob,
    syncBubblesToBackend,
    bumpPageVersion: pagesApi.bumpPageVersion,
    loadPagesFromServer,
    showAlert,
    t,
  });

  const { backendError, isRetryingBackend, handleRetryBackend } = useBackendBootstrap({
    setSettings,
    loadPagesFromServer,
  });

  useAppChrome({ openSettings: () => setIsSettingsOpen(true) });

  const {
    guardUnsaved,
    handleNewProject,
    handleOpenProject,
    handleImportImages,
    handleDeletePage,
    handleRenamePage,
  } = useProjectActions({
    isDirty,
    showUnsavedPrompt,
    saveProject: projectApi.handleSaveProject,
    newProject: projectApi.handleNewProject,
    loadProject: projectApi.handleLoadProject,
    openFiles: projectApi.handleOpenFiles,
    pages,
    selectedPageIds,
    runTask,
    loadPagesFromServer,
    currentIndexRef,
    markDirty,
    resetPageVersions: pagesApi.resetPageVersions,
    selectPage: pagesApi.handleSelectPage,
    deletePages: pagesApi.handleDeletePages,
    setSelectedPageIds,
    setSelectedBubbleId,
    t,
  });

  useWindowCloseGuard(isDirty, guardUnsaved);

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

  return (
    <div className="app-container">
      <Toolbar
        onNewProject={handleNewProject}
        onOpenProject={handleOpenProject}
        onSaveProject={projectApi.handleSaveProject}
        onPreferences={() => setIsSettingsOpen(true)}
        onAbout={() => setIsAboutOpen(true)}
        isDirty={isDirty}
        t={t}
      />

      <div className="main-workspace">
        <Sidebar
          pages={pages}
          currentIndex={currentIndex}
          selectedPageIds={selectedPageIds}
          pageVersions={pagesApi.pageVersions}
          onSelectPage={pagesApi.handleSelectPage}
          onPageClick={handlePageSelection}
          onSelectAllPages={handleSelectAllPages}
          onDuplicatePage={(idx) => pagesApi.handleDuplicatePages(resolveContextTargets(idx))}
          onDeletePage={handleDeletePage}
          onReorderPages={pagesApi.handleReorderPages}
          onImportImages={handleImportImages}
          onExportSelectedImages={() => handleExportPages(selectedPageIds)}
          onRenamePage={handleRenamePage}
          onTranslatePages={handleContextTranslate}
          onSaveImages={handleContextSaveImages}
          backendUrl={currentBackendUrl}
          t={t}
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
          t={t}
        />

        <Inspector
          selectedBubble={activeBubble}
          settings={settings}
          onUpdateBubble={bubblesApi.handleUpdateBubble}
          onReOcrBubble={bubblesApi.handleReOcrBubble}
          onReTranslateBubble={bubblesApi.handleReTranslateBubble}
          isProcessing={isProcessing}
          isMultiPageSelection={isMultiPageSelection}
          t={t}
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
        t={t}
      />

      <InitialSetupModal
        isOpen={!backendError && settings.setup_completed === false}
        settings={settings}
        onComplete={setSettings}
      />

      <CustomDialog options={dialog} onClose={closeDialog} t={t} />

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
