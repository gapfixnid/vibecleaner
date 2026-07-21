// frontend/src/components/Toolbar.tsx
import React, { useEffect, useRef, useState } from "react";
import { FilePlus2, FolderOpen, Info, Menu, Minus, Save, Settings, Square, X } from "lucide-react";
import * as desktop from "../services/desktop";
import { APP_NAME } from "../appMeta";

interface ToolbarProps {
  onNewProject: () => void;
  onOpenProject: () => void;
  onSaveProject: () => void;
  onPreferences: () => void;
  onAbout: () => void;
  isDirty: boolean;
  t?: (key: string) => string;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  onNewProject,
  onOpenProject,
  onSaveProject,
  onPreferences,
  onAbout,
  isDirty,
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
    menuRef.current?.querySelector<HTMLButtonElement>("[role='menuitem']:not(:disabled)")?.focus();
  }, [menuOpen]);

  const handleMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("[role='menuitem']:not(:disabled)") ?? []);
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
      <div className="toolbar-left" data-tauri-drag-region>
        <span className="logo-text" data-tauri-drag-region>{APP_NAME}</span>
      </div>

      <div className="drag-spacer" data-tauri-drag-region />

      <div className="toolbar-right">
        <div className="menu-wrapper app-menu-wrapper" ref={menuRef}>
          <button
            type="button"
            className={`app-menu-button ${menuOpen ? "active" : ""}`}
            aria-label={t("toolbar.menu")}
            aria-haspopup="menu"
            aria-controls="toolbar-dropdown-menu"
            aria-expanded={menuOpen}
            ref={menuButtonRef}
            onClick={() => setMenuOpen((open) => !open)}
            onKeyDown={(event) => {
              if ((event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") && !menuOpen) {
                event.preventDefault();
                setMenuOpen(true);
              }
            }}
          >
            <Menu size={16} />
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
              <button type="button" role="menuitem" onClick={runItem(onSaveProject)}>
                <Save size={14} />
                <span>{t("toolbar.saveProject")}</span>
                {isDirty && <span className="toolbar-unsaved-dot" aria-hidden="true" />}
              </button>
              <div className="toolbar-menu-separator" role="separator" />
              <button type="button" role="menuitem" onClick={runItem(onPreferences)}>
                <Settings size={14} />
                <span>{t("toolbar.preferences")}</span>
              </button>
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
          padding: 0 12px 0 12px;
          z-index: 10;
          user-select: none;
          font-family: var(--font-family);
        }

        .window-controls {
          display: flex;
          height: 100%;
          gap: 0;
          margin-left: 0;
          margin-right: -12px;
          align-items: stretch;
          pointer-events: auto;
        }

        .win-btn {
          width: 46px;
          flex: 0 0 46px;
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
          gap: 0;
          min-width: 0;
        }

        .toolbar-right {
          height: 100%;
          justify-content: flex-end;
          pointer-events: auto;
        }

        .toolbar-unsaved-dot {
          width: 5px;
          height: 5px;
          border-radius: var(--radius-full);
          background: var(--system-orange);
        }

        .app-menu-button {
          width: 38px;
          height: 100%;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex: 0 0 auto;
          color: var(--text-secondary);
          background: transparent;
          border: none;
          border-radius: 0;
          padding: 0;
          cursor: pointer;
          transition: background-color 0.12s ease, color 0.12s ease;
        }

        .app-menu-button:hover,
        .app-menu-button.active {
          background: var(--fill-hover);
          color: var(--text-primary);
        }

        .app-menu-button:focus-visible {
          outline: 2px solid var(--system-blue);
          outline-offset: 2px;
        }

        .logo-text {
          font-weight: 650;
          font-size: 15px;
          letter-spacing: 0;
          line-height: 1;
          color: var(--text-primary);
        }

        .menu-wrapper {
          position: relative;
          height: 100%;
          pointer-events: auto;
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

        .toolbar-menu button:disabled {
          opacity: 0.4;
          cursor: default;
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

      `}</style>
    </header>
  );
};
