// frontend/src/components/BackendErrorScreen.tsx
import React, { useMemo } from "react";
import { ServerCrash, RotateCcw } from "lucide-react";
import { createTranslator, getStoredUiLanguage } from "../i18n";
import type { BackendErrorInfo } from "../hooks/useBackendBootstrap";

interface BackendErrorScreenProps {
  error: BackendErrorInfo;
  isRetrying: boolean;
  onRetry: () => void;
}

/**
 * In-app recoverable error screen shown when the Python backend fails to start.
 * Rendered with the app's own design language (not a native dialog) so the
 * visual identity is preserved. Webview-level failures that prevent React from
 * rendering at all are handled by a last-resort native message in the Rust layer.
 *
 * The backend (and thus `settings.ui_language`) is unavailable here, so the
 * translator falls back to the language remembered in localStorage.
 */
export const BackendErrorScreen: React.FC<BackendErrorScreenProps> = ({ error, isRetrying, onRetry }) => {
  const t = useMemo(() => createTranslator(getStoredUiLanguage()), []);
  const description =
    error.code === "unreachable"
      ? t("backend.unreachable")
      : error.code === "restart_failed"
        ? t("backend.restartFailed")
        : t("backend.startFailedDesc");

  return (
    <div className="backend-error-overlay">
      <div className="backend-error-card">
        <ServerCrash size={40} className="backend-error-icon" />
        <h2 className="backend-error-title">{t("backend.startFailedTitle")}</h2>
        <p className="backend-error-desc">{description}</p>
        {error.detail && <pre className="backend-error-detail">{error.detail}</pre>}
        <button className="backend-error-retry" onClick={onRetry} disabled={isRetrying}>
          <RotateCcw size={15} className={isRetrying ? "spinning" : ""} />
          <span>{isRetrying ? t("backend.retrying") : t("backend.retry")}</span>
        </button>
      </div>

      <style>{`
        .backend-error-overlay {
          position: fixed;
          top: var(--toolbar-height, 0px);
          left: 0;
          right: 0;
          bottom: 0;
          background: var(--bg-canvas, #1e1e1e);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 10000;
          padding: 24px;
        }

        .backend-error-card {
          background: var(--bg-panel);
          border: 1px solid var(--border-color);
          border-radius: 16px;
          padding: 32px;
          width: 460px;
          max-width: 100%;
          box-shadow: var(--shadow-lg);
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: 14px;
        }

        .backend-error-icon {
          color: var(--system-red);
        }

        .backend-error-title {
          font-size: 17px;
          font-weight: 600;
          color: var(--text-primary);
          letter-spacing: -0.2px;
          margin: 0;
        }

        .backend-error-desc {
          font-size: 13px;
          line-height: 1.6;
          color: var(--text-secondary);
          margin: 0;
          word-break: keep-all;
        }

        .backend-error-detail {
          width: 100%;
          max-height: 140px;
          overflow: auto;
          background: var(--inset-bg);
          border: 1px solid var(--border-color);
          border-radius: 10px;
          padding: 10px 12px;
          font-size: 11px;
          line-height: 1.5;
          color: var(--text-secondary);
          white-space: pre-wrap;
          text-align: left;
          margin: 0;
        }

        .backend-error-retry {
          margin-top: 6px;
          display: flex;
          align-items: center;
          gap: 8px;
          background: var(--system-blue);
          color: #fff;
          border: none;
          border-radius: 20px;
          padding: 9px 20px;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: background var(--transition-base);
        }

        .backend-error-retry:hover:not(:disabled) {
          background: var(--system-blue-hover, #0a84ff);
        }

        .backend-error-retry:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .backend-error-retry .spinning {
          animation: backendSpin 0.8s linear infinite;
        }

        @keyframes backendSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
