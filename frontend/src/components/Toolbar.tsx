// frontend/src/components/Toolbar.tsx
import React, { useEffect, useRef, useState } from "react";
import { Download, FilePlus2, FolderOpen, ImagePlus, Info, Menu, Minus, PanelRightClose, PanelRightOpen, Save, Settings, Square, X } from "lucide-react";
import * as desktop from "../services/desktop";
import { APP_NAME } from "../appMeta";

interface ToolbarProps {
  onNewProject: () => void;
  onOpenProject: () => void;
  onSaveProject: () => void;
  onImportImages: () => void;
  onExport: () => void;
  onPreferences: () => void;
  onAbout: () => void;
  onToggleInspector: () => void;
  isInspectorOpen: boolean;
  isDirty: boolean;
  canExport: boolean;
  t?: (key: string) => string;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  onNewProject,
  onOpenProject,
  onSaveProject,
  onImportImages,
  onExport,
  onPreferences,
  onAbout,
  onToggleInspector,
  isInspectorOpen,
  isDirty,
  canExport,
  t = (key) => key,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;
    menuRef.current?.querySelector<HTMLButtonElement>("[role='menuitem']")?.focus();
  }, [menuOpen]);

  const handleMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("[role='menuitem']") ?? []);
    if (items.length === 0) return;
    const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
    let nextIndex: number | null = null;
    if (event.key === "ArrowDown") nextIndex = (currentIndex + 1) % items.length;
    else if (event.key === "ArrowUp") nextIndex = (currentIndex - 1 + items.length) % items.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = items.length - 1;
    else if (event.key === "Escape") {
      event.preventDefault();
      setMenuOpen(false);
      menuButtonRef.current?.focus();
      return;
    }
    if (nextIndex !== null) {
      event.preventDefault();
      items[nextIndex].focus();
    }
  };

  const runItem = (fn: () => void) => () => {
    setMenuOpen(false);
    fn();
  };

  return (
    <header className="toolbar-container">
      <div className="toolbar-left">
        <div className="app-logo" data-tauri-drag-region>
          <span className="app-mark" aria-hidden="true">
            <img className="app-icon" src="/favicon.svg" alt="" draggable={false} />
          </span>
          <div className="app-title-stack" data-tauri-drag-region>
            <span className="logo-text" data-tauri-drag-region>{APP_NAME}</span>
            <span className="toolbar-subtitle" data-tauri-drag-region>{t("toolbar.subtitle")}</span>
          </div>
        </div>
      </div>

      <div className="drag-spacer" data-tauri-drag-region />

      <div className="toolbar-right">
        <button type="button" className="toolbar-command" onClick={onImportImages}>
          <ImagePlus size={15} />
          <span>{t("toolbar.addImages")}</span>
        </button>
        <button
          type="button"
          className={`toolbar-command ${isDirty ? "has-change" : ""}`}
          onClick={onSaveProject}
          data-tooltip={isDirty ? t("statusbar.unsaved") : t("toolbar.saveProject")}
        >
          <Save size={15} />
          <span>{t("toolbar.saveProject")}</span>
          {isDirty && <span className="toolbar-unsaved-dot" aria-hidden="true" />}
        </button>
        <button type="button" className="toolbar-command" onClick={onExport} disabled={!canExport}>
          <Download size={15} />
          <span>{t("toolbar.export")}</span>
        </button>
        <button
          type="button"
          className="toolbar-action settings-shortcut"
          onClick={onPreferences}
          data-tooltip={t("toolbar.preferences")}
          aria-label={t("toolbar.preferences")}
        >
          <Settings size={17} />
        </button>
        <button
          type="button"
          className="toolbar-action inspector-toggle"
          onClick={onToggleInspector}
          data-tooltip={t(isInspectorOpen ? "layout.hideInspector" : "layout.showInspector")}
          aria-label={t(isInspectorOpen ? "layout.hideInspector" : "layout.showInspector")}
          aria-pressed={isInspectorOpen}
        >
          {isInspectorOpen ? <PanelRightClose size={17} /> : <PanelRightOpen size={17} />}
        </button>
        <div className="menu-wrapper" ref={menuRef}>
          <button
            type="button"
            className={`toolbar-action menu-toggle ${menuOpen ? "active" : ""}`}
            data-tooltip={t("toolbar.menu")}
            aria-label={t("toolbar.menu")}
            aria-haspopup="menu"
            aria-controls="toolbar-dropdown-menu"
            aria-expanded={menuOpen}
            ref={menuButtonRef}
            onClick={() => setMenuOpen((v) => !v)}
            onKeyDown={(event) => {
              if ((event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") && !menuOpen) {
                event.preventDefault();
                setMenuOpen(true);
              }
            }}
          >
            <Menu size={18} />
          </button>

          {menuOpen && (
            <div id="toolbar-dropdown-menu" className="toolbar-menu" role="menu" onKeyDown={handleMenuKeyDown}>
              <button type="button" role="menuitem" onClick={runItem(onNewProject)}>
                <FilePlus2 size={14} />
                <span>{t("toolbar.newProject")}</span>
              </button>
              <button type="button" role="menuitem" onClick={runItem(onOpenProject)}>
                <FolderOpen size={14} />
                <span>{t("toolbar.openProject")}</span>
              </button>
              <div className="toolbar-menu-separator" role="separator" />
              <button type="button" role="menuitem" onClick={runItem(onAbout)}>
                <Info size={14} />
                <span>{t("toolbar.about")}</span>
              </button>
            </div>
          )}
        </div>
        <div className="window-controls">
          <button type="button" className="win-btn" onClick={() => desktop.minimizeWindow()} aria-label={t("toolbar.minimizeWindow")}>
            <Minus size={13} />
          </button>
          <button type="button" className="win-btn" onClick={() => desktop.toggleMaximizeWindow()} aria-label={t("toolbar.maximizeWindow")}>
            <Square size={10} />
          </button>
          <button type="button" className="win-btn close" onClick={() => desktop.closeWindow()} aria-label={t("toolbar.closeWindow")}>
            <X size={13} />
          </button>
        </div>
      </div>

      <style>{`
        .toolbar-container {
          height: var(--toolbar-height);
          background: var(--bg-toolbar);
          backdrop-filter: var(--glass-blur);
          -webkit-backdrop-filter: var(--glass-blur);
          border-bottom: 1px solid var(--border-color);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 12px 0 14px;
          z-index: 10;
          user-select: none;
          font-family: var(--font-family);
        }

        .window-controls {
          display: flex;
          align-self: stretch;
          gap: 0;
          margin-left: 4px;
          margin-right: -12px;
          align-items: center;
          pointer-events: auto;
        }

        .win-btn {
          width: 42px;
          height: 100%;
          border-radius: 0;
          border: none;
          background: transparent;
          color: var(--text-secondary);
          cursor: pointer;
          position: relative;
          padding: 0;
          transition: background-color 0.12s ease, color 0.12s ease;
          pointer-events: auto;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .win-btn:hover {
          background: var(--fill-hover);
          color: var(--text-primary);
        }

        .win-btn:active {
          background: var(--fill-1);
        }

        .win-btn.close:hover {
          background: #c42b1c;
          color: #fff;
        }

        .drag-spacer {
          flex: 1;
          height: 100%;
          cursor: default;
        }

        .toolbar-left, .toolbar-right {
          display: flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
        }

        .toolbar-right {
          justify-content: flex-end;
          pointer-events: auto;
        }

        .toolbar-command {
          height: 30px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          padding: 0 10px;
          border: 1px solid transparent;
          border-radius: 8px;
          background: transparent;
          color: var(--text-secondary);
          font: 600 11.5px/1 var(--font-family);
          cursor: pointer;
          transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
        }

        .toolbar-command:hover:not(:disabled) {
          background: var(--fill-hover);
          border-color: var(--border-color);
          color: var(--text-primary);
        }

        .toolbar-command:disabled {
          opacity: 0.38;
          cursor: default;
        }

        .toolbar-command.has-change {
          color: var(--text-primary);
        }

        .toolbar-unsaved-dot {
          width: 5px;
          height: 5px;
          border-radius: var(--radius-full);
          background: var(--system-orange);
        }

        .settings-shortcut {
          margin-left: 2px;
        }

        .app-logo {
          display: flex;
          align-items: center;
          gap: 11px;
          min-width: 0;
        }

        .app-mark {
          width: 36px;
          height: 36px;
          border-radius: 10px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex: 0 0 auto;
          background: var(--fill-2);
          border: 1px solid var(--overlay-border);
          box-shadow: var(--control-active-shadow);
          overflow: hidden;
        }

        .app-icon {
          width: 27px;
          height: 27px;
          display: block;
          object-fit: contain;
          user-select: none;
          -webkit-user-drag: none;
        }

        .app-title-stack {
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 1px;
          min-width: 0;
        }

        .logo-text {
          font-weight: 650;
          font-size: 17px;
          letter-spacing: 0;
          line-height: 1.05;
          color: var(--text-primary);
        }

        .toolbar-subtitle {
          color: var(--text-tertiary);
          font-size: 10.5px;
          font-weight: 500;
          line-height: 1.1;
          white-space: nowrap;
        }

        .menu-wrapper {
          position: relative;
          pointer-events: auto;
        }

        .toolbar-action {
          width: 26px;
          height: 26px;
          border: 1px solid transparent;
          background: transparent;
          color: var(--text-secondary);
          cursor: pointer;
          border-radius: 7px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          transition:
            background-color 0.16s ease,
            border-color 0.16s ease,
            color 0.16s ease,
            box-shadow 0.16s ease,
            transform 0.12s ease;
        }

        .toolbar-action:hover {
          background: var(--fill-hover);
          border-color: var(--border-color);
          color: var(--text-primary);
        }

        .toolbar-action:active {
          transform: translateY(1px) scale(0.98);
        }

        .toolbar-action.primary {
          background: var(--system-blue);
          border-color: transparent;
          color: white;
          box-shadow: var(--accent-glow);
        }

        .toolbar-action.primary:hover {
          background: var(--system-blue-hover);
          color: white;
        }

        .toolbar-action.menu-toggle {
          width: 30px;
          height: 30px;
          border-radius: 9px;
          background: var(--fill-3);
          border-color: var(--border-color);
        }

        .toolbar-action.active {
          background: var(--control-active-bg);
          color: var(--text-primary);
          box-shadow: var(--control-active-shadow);
        }

        .toolbar-menu {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          min-width: 184px;
          background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02)),
            var(--bg-panel);
          border: 1px solid var(--border-color);
          border-radius: 11px;
          box-shadow: var(--shadow-lg);
          padding: 6px;
          display: flex;
          flex-direction: column;
          gap: 2px;
          z-index: 100;
          transform-origin: top right;
          will-change: opacity, transform;
          animation: toolbarMenuEnter 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes toolbarMenuEnter {
          0% {
            opacity: 0;
            transform: translateX(14px) translateY(-4px) scale(0.96);
          }
          62% {
            opacity: 1;
            transform: translateX(-2px) translateY(0) scale(1.01);
          }
          100% {
            opacity: 1;
            transform: translateX(0) translateY(0) scale(1);
          }
        }

        .toolbar-menu button {
          display: flex;
          align-items: center;
          gap: 10px;
          width: 100%;
          padding: 7px 10px;
          border: none;
          background: transparent;
          color: var(--text-primary);
          font-size: 13px;
          font-weight: 500;
          font-family: var(--font-family);
          text-align: left;
          border-radius: 6px;
          cursor: pointer;
          transition: background-color 0.14s ease, color 0.14s ease;
        }

        .toolbar-menu button:hover {
          background: var(--fill-hover, var(--bg-input));
        }

        .toolbar-menu button svg {
          color: var(--text-secondary);
          flex-shrink: 0;
        }

        .toolbar-menu-separator {
          height: 1px;
          background: var(--border-color);
          margin: 4px 6px;
        }

        @media (max-width: 760px) {
          .toolbar-subtitle {
            display: none;
          }

          .toolbar-command span {
            display: none;
          }

          .toolbar-command {
            width: 30px;
            padding: 0;
          }
        }
      `}</style>
    </header>
  );
};
