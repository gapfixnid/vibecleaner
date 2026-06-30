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

  return (
    <header className="toolbar-container">
      <div className="toolbar-left">
        <div className="window-controls">
          <button type="button" className="win-btn close" onClick={() => desktop.closeWindow()} aria-label="Close window" />
          <button type="button" className="win-btn minimize" onClick={() => desktop.minimizeWindow()} aria-label="Minimize window" />
          <button type="button" className="win-btn maximize" onClick={() => desktop.toggleMaximizeWindow()} aria-label="Maximize window" />
        </div>

        <div className="app-logo" data-tauri-drag-region>
          <span className="app-mark" aria-hidden="true">V</span>
          <div className="app-title-stack" data-tauri-drag-region>
            <span className="logo-text" data-tauri-drag-region>{APP_NAME}</span>
            <span className="toolbar-subtitle" data-tauri-drag-region>Image cleanup workspace</span>
          </div>
        </div>
      </div>

      <div className="drag-spacer" data-tauri-drag-region />

      <div className="toolbar-right">
        <div className={`save-state ${isDirty ? "dirty" : "clean"}`} aria-live="polite">
          <span className="save-state-dot" aria-hidden="true" />
          <span>{isDirty ? "Unsaved changes" : "Saved"}</span>
        </div>

        <div className="toolbar-command-group" role="group" aria-label="Project actions">
          <button type="button" className="toolbar-action" data-tooltip="New Project" onClick={onNewProject} aria-label="New Project">
            <FilePlus2 size={15} />
          </button>
          <button type="button" className="toolbar-action" data-tooltip="Open Project" onClick={onOpenProject} aria-label="Open Project">
            <FolderOpen size={15} />
          </button>
          <button
            type="button"
            className={`toolbar-action ${isDirty ? "primary" : ""}`}
            data-tooltip="Save Project"
            onClick={onSaveProject}
            aria-label="Save Project"
          >
            <Save size={15} />
          </button>
        </div>

        <button
          type="button"
          className="toolbar-action standalone"
          data-tooltip="Preferences"
          onClick={onPreferences}
          aria-label="Preferences"
        >
          <Settings size={15} />
        </button>

        <div className="menu-wrapper" ref={menuRef}>
          <button
            type="button"
            className={`toolbar-action standalone ${menuOpen ? "active" : ""}`}
            data-tooltip="More"
            aria-label="Menu"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <Menu size={18} />
          </button>

          {menuOpen && (
            <div className="toolbar-menu" role="menu">
              <button role="menuitem" onClick={runItem(onNewProject)}>
                <FilePlus2 size={14} />
                <span>New Project</span>
              </button>
              <button role="menuitem" onClick={runItem(onOpenProject)}>
                <FolderOpen size={14} />
                <span>Open Project</span>
              </button>
              <button role="menuitem" onClick={runItem(onSaveProject)}>
                <Save size={14} />
                <span>Save Project</span>
              </button>
              <div className="toolbar-menu-separator" />
              <button role="menuitem" onClick={runItem(onPreferences)}>
                <Settings size={14} />
                <span>Preferences</span>
              </button>
              <button role="menuitem" onClick={runItem(onAbout)}>
                <Info size={14} />
                <span>About</span>
              </button>
            </div>
          )}
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
          gap: 9px;
          min-width: 0;
        }

        .app-mark {
          width: 24px;
          height: 24px;
          border-radius: 7px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex: 0 0 auto;
          background:
            linear-gradient(145deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.04)),
            var(--fill-2);
          border: 1px solid var(--overlay-border);
          box-shadow: var(--control-active-shadow);
          color: var(--text-primary);
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 0;
          line-height: 1;
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
          font-size: 14px;
          letter-spacing: 0;
          line-height: 1.1;
          color: var(--text-primary);
        }

        .toolbar-subtitle {
          color: var(--text-tertiary);
          font-size: 10.5px;
          font-weight: 500;
          line-height: 1.1;
          white-space: nowrap;
        }

        .save-state {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          height: 26px;
          padding: 0 9px;
          border: 1px solid var(--border-color);
          border-radius: var(--radius-full);
          background: var(--fill-3);
          color: var(--text-secondary);
          font-size: 11.5px;
          font-weight: 600;
          white-space: nowrap;
          font-variant-numeric: tabular-nums;
        }

        .save-state-dot {
          width: 6px;
          height: 6px;
          border-radius: var(--radius-full);
          background: var(--system-green);
          box-shadow: 0 0 0 3px rgba(52, 199, 89, 0.10);
        }

        .save-state.dirty {
          color: var(--text-primary);
          background: rgba(255, 149, 0, 0.12);
          border-color: rgba(255, 149, 0, 0.28);
        }

        .save-state.dirty .save-state-dot {
          background: var(--system-orange);
          box-shadow: 0 0 0 3px rgba(255, 149, 0, 0.14);
        }

        .menu-wrapper {
          position: relative;
          pointer-events: auto;
        }

        .toolbar-command-group {
          display: inline-flex;
          align-items: center;
          gap: 2px;
          height: 30px;
          padding: 2px;
          border: 1px solid var(--border-color);
          border-radius: 9px;
          background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02)),
            var(--fill-4);
          box-shadow: var(--inset-track-shadow);
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

        .toolbar-action.standalone {
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
          animation: dialogFadeIn 0.1s ease-out;
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

        .toolbar-divider {
          width: 1px;
          height: 20px;
          background-color: var(--border-color);
        }

        @media (max-width: 760px) {
          .toolbar-subtitle,
          .save-state {
            display: none;
          }
        }
      `}</style>
    </header>
  );
};
