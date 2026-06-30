// frontend/src/components/Toolbar.tsx
import React, { useEffect, useRef, useState } from "react";
import { FilePlus2, FolderOpen, Info, Menu, Save, Settings } from "lucide-react";
import * as desktop from "../services/desktop";
import { APP_NAME } from "../appMeta";

interface ToolbarProps {
  onNewProject: () => void;
  onOpenProject: () => void;
  onSaveProject: () => void;
  onPreferences: () => void;
  onAbout: () => void;
  isDirty: boolean;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  onNewProject,
  onOpenProject,
  onSaveProject,
  onPreferences,
  onAbout,
  isDirty,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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

  const runItem = (fn: () => void) => () => {
    setMenuOpen(false);
    fn();
  };
  const menuItemTabIndex = menuOpen ? 0 : -1;

  return (
    <header className="toolbar-container">
      <div className="toolbar-left">
        <div className="window-controls">
          <button type="button" className="win-btn close" onClick={() => desktop.closeWindow()} aria-label="Close window" />
          <button type="button" className="win-btn minimize" onClick={() => desktop.minimizeWindow()} aria-label="Minimize window" />
          <button type="button" className="win-btn maximize" onClick={() => desktop.toggleMaximizeWindow()} aria-label="Maximize window" />
        </div>

        <div className="app-logo" data-tauri-drag-region>
          <span className="app-mark" aria-hidden="true">
            <img className="app-icon" src="/favicon.svg" alt="" draggable={false} />
          </span>
          <div className="app-title-stack" data-tauri-drag-region>
            <span className="logo-text" data-tauri-drag-region>{APP_NAME}</span>
            <span className="toolbar-subtitle" data-tauri-drag-region>Image cleanup workspace</span>
          </div>
        </div>
      </div>

      <div className="drag-spacer" data-tauri-drag-region />

      <div className="toolbar-right">
        <div className={`menu-wrapper ${menuOpen ? "open" : ""}`} ref={menuRef}>
          <div
            id="toolbar-action-flyout"
            className="toolbar-flyout"
            role="menu"
            aria-label="Project actions"
            aria-hidden={!menuOpen}
          >
            <button type="button" className="flyout-action" role="menuitem" tabIndex={menuItemTabIndex} onClick={runItem(onNewProject)}>
              <FilePlus2 size={14} />
              <span>New</span>
            </button>
            <button type="button" className="flyout-action" role="menuitem" tabIndex={menuItemTabIndex} onClick={runItem(onOpenProject)}>
              <FolderOpen size={14} />
              <span>Open</span>
            </button>
            <button
              type="button"
              className={`flyout-action ${isDirty ? "primary" : ""}`}
              role="menuitem"
              tabIndex={menuItemTabIndex}
              onClick={runItem(onSaveProject)}
            >
              <Save size={14} />
              <span>Save</span>
            </button>
            <button type="button" className="flyout-action" role="menuitem" tabIndex={menuItemTabIndex} onClick={runItem(onPreferences)}>
              <Settings size={14} />
              <span>Preferences</span>
            </button>
            <button type="button" className="flyout-action" role="menuitem" tabIndex={menuItemTabIndex} onClick={runItem(onAbout)}>
              <Info size={14} />
              <span>About</span>
            </button>
          </div>
          <button
            type="button"
            className={`toolbar-action menu-toggle ${menuOpen ? "active" : ""}`}
            data-tooltip={menuOpen ? "Close" : "Menu"}
            aria-label={menuOpen ? "Close Menu" : "Open Menu"}
            aria-haspopup="menu"
            aria-controls="toolbar-action-flyout"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <Menu size={18} />
          </button>
        </div>
      </div>

      <style>{`
        .toolbar-container {
          height: var(--toolbar-height);
          background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.10), rgba(255, 255, 255, 0.02)),
            var(--bg-toolbar);
          backdrop-filter: var(--glass-blur);
          -webkit-backdrop-filter: var(--glass-blur);
          border-bottom: 1px solid var(--border-color);
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
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
          gap: 8px;
          margin-right: 14px;
          align-items: center;
          pointer-events: auto;
        }

        .win-btn {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          border: none;
          cursor: pointer;
          position: relative;
          padding: 0;
          box-shadow: inset 0 0 0 0.5px rgba(0, 0, 0, 0.18);
          transition: filter 0.12s ease, transform 0.12s ease;
          pointer-events: auto;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .win-btn:hover {
          filter: brightness(0.85);
        }

        .win-btn:active {
          transform: scale(0.92);
        }

        .win-btn.close {
          background-color: #ff5f56;
        }

        .win-btn.minimize {
          background-color: #ffbd2e;
        }

        .win-btn.maximize {
          background-color: #27c93f;
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
          background:
            linear-gradient(145deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.04)),
            var(--fill-2);
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
          display: inline-flex;
          align-items: center;
          gap: 6px;
          pointer-events: auto;
        }

        .toolbar-flyout {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          height: 32px;
          max-width: 0;
          overflow: hidden;
          padding: 0;
          border: 1px solid transparent;
          border-radius: 10px;
          background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02)),
            var(--fill-4);
          box-shadow: none;
          opacity: 0;
          pointer-events: none;
          transform: translateX(18px) scaleX(0.94);
          transform-origin: right center;
          white-space: nowrap;
          will-change: max-width, opacity, transform;
          transition:
            max-width 0.34s cubic-bezier(0.16, 1, 0.3, 1),
            opacity 0.18s ease,
            transform 0.34s cubic-bezier(0.16, 1, 0.3, 1),
            padding 0.34s cubic-bezier(0.16, 1, 0.3, 1),
            border-color 0.18s ease,
            box-shadow 0.18s ease;
        }

        .menu-wrapper.open .toolbar-flyout {
          max-width: 440px;
          padding: 3px;
          border-color: var(--border-color);
          box-shadow: var(--inset-track-shadow);
          opacity: 1;
          pointer-events: auto;
          transform: translateX(0) scaleX(1);
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
          box-shadow: 0 5px 14px rgba(0, 122, 255, 0.22);
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

        .flyout-action {
          height: 26px;
          border: 1px solid transparent;
          border-radius: 7px;
          background: transparent;
          color: var(--text-secondary);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          padding: 0 9px;
          font-family: var(--font-family);
          font-size: 12px;
          font-weight: 600;
          white-space: nowrap;
          opacity: 0;
          transform: translateX(8px);
          will-change: opacity, transform;
          transition:
            background-color 0.14s ease,
            border-color 0.14s ease,
            color 0.14s ease,
            opacity 0.22s ease,
            transform 0.24s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .menu-wrapper.open .flyout-action {
          opacity: 1;
          transform: translateX(0);
          transition-delay: 0.05s;
        }

        .flyout-action:hover {
          background: var(--fill-hover, var(--bg-input));
          border-color: var(--border-color);
          color: var(--text-primary);
        }

        .flyout-action svg {
          color: var(--text-secondary);
          flex-shrink: 0;
        }

        .flyout-action.primary {
          background: var(--system-blue);
          border-color: transparent;
          color: white;
          box-shadow: 0 5px 14px rgba(0, 122, 255, 0.22);
        }

        .flyout-action.primary svg {
          color: white;
        }

        @media (max-width: 760px) {
          .toolbar-subtitle {
            display: none;
          }

          .menu-wrapper.open .toolbar-flyout {
            max-width: 230px;
          }

          .flyout-action {
            width: 28px;
            padding: 0;
          }

          .flyout-action span {
            display: none;
          }
        }
      `}</style>
    </header>
  );
};
