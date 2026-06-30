// frontend/src/components/Toolbar.tsx
import React, { useEffect, useRef, useState } from "react";
import { Menu, FilePlus2, FolderOpen, Save, Settings, Info } from "lucide-react";
import * as desktop from "../services/desktop";
import { APP_NAME } from "../appMeta";

interface ToolbarProps {
  onNewProject: () => void;
  onOpenProject: () => void;
  onSaveProject: () => void;
  onPreferences: () => void;
  onAbout: () => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  onNewProject,
  onOpenProject,
  onSaveProject,
  onPreferences,
  onAbout,
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
        {/* macOS Style Traffic Lights Window Controls */}
        <div className="window-controls">
          <button type="button" className="win-btn close" onClick={() => desktop.closeWindow()} aria-label="Close window" />
          <button type="button" className="win-btn minimize" onClick={() => desktop.minimizeWindow()} aria-label="Minimize window" />
          <button type="button" className="win-btn maximize" onClick={() => desktop.toggleMaximizeWindow()} aria-label="Maximize window" />
        </div>

        <div className="app-logo" data-tauri-drag-region>
          <span className="logo-text" data-tauri-drag-region>{APP_NAME}</span>
        </div>
      </div>

      <div className="drag-spacer" data-tauri-drag-region />

      <div className="toolbar-right">
        <div className="menu-wrapper" ref={menuRef}>
          <button
            type="button"
            className="icon-btn"
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
          background-color: var(--bg-toolbar);
          backdrop-filter: var(--glass-blur);
          border-bottom: 1px solid var(--border-color);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 16px;
          z-index: 10;
          user-select: none;
        }

        .window-controls {
          display: flex;
          gap: 8px;
          margin-right: 12px;
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
          transition: filter 0.1s;
          pointer-events: auto;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .win-btn:hover {
          filter: brightness(0.85);
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
          gap: 12px;
        }

        .toolbar-right {
          justify-content: flex-end;
        }

        .app-logo {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .logo-icon {
          color: var(--text-secondary);
        }

        .logo-text {
          font-weight: 700;
          font-size: 14px;
          letter-spacing: -0.3px;
        }

        .menu-wrapper {
          position: relative;
          pointer-events: auto;
        }

        .toolbar-menu {
          position: absolute;
          top: calc(100% + 6px);
          right: 0;
          min-width: 184px;
          background: var(--bg-panel);
          border: 1px solid var(--border-color);
          border-radius: 10px;
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
          font-family: var(--font-family);
          text-align: left;
          border-radius: 6px;
          cursor: pointer;
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

        .icon-btn {
          background: transparent;
          border: none;
          color: var(--text-secondary);
          cursor: pointer;
          padding: 6px;
          border-radius: var(--radius-md);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
        }

        .icon-btn:hover {
          background: var(--bg-input);
          color: var(--text-primary);
        }

        .toolbar-divider {
          width: 1px;
          height: 20px;
          background-color: var(--border-color);
        }
      `}</style>
    </header>
  );
};
