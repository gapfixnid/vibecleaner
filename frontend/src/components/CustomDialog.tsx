// frontend/src/components/CustomDialog.tsx
import React, { useEffect, useRef } from "react";
import { AlertTriangle, CheckCircle, HelpCircle, Info, XCircle } from "lucide-react";

export interface DialogOptions {
  isOpen: boolean;
  type: "info" | "success" | "warning" | "error" | "confirm";
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel?: () => void;
  /** Optional third "deny" action (e.g. "Don't Save"). When set, the confirm
   *  dialog renders three buttons: Cancel / Deny / Confirm. */
  onDeny?: () => void;
  denyText?: string;
  confirmText?: string;
  cancelText?: string;
  /** Render the confirm button as destructive (red). Falls back to a title heuristic. */
  destructive?: boolean;
}

interface CustomDialogProps {
  options: DialogOptions;
  onClose: () => void;
  t?: (key: string) => string;
}

export const CustomDialog: React.FC<CustomDialogProps> = ({ options, onClose, t = (key) => key }) => {
  const boxRef = useRef<HTMLDivElement>(null);

  const handleConfirm = () => {
    options.onConfirm();
    onClose();
  };

  const handleCancel = () => {
    if (options.onCancel) {
      options.onCancel();
    }
    onClose();
  };

  const handleDeny = () => {
    if (options.onDeny) {
      options.onDeny();
    }
    onClose();
  };

  // Escape to dismiss + move focus into the dialog + trap Tab within it.
  useEffect(() => {
    if (!options.isOpen) return;
    const box = boxRef.current;
    const focusables = box
      ? Array.from(
          box.querySelectorAll<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")
        )
      : [];
    (focusables[focusables.length - 1] ?? box)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleCancel();
      } else if (e.key === "Tab" && focusables.length > 0) {
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.isOpen]);

  if (!options.isOpen) return null;

  // Get icon based on type
  const getIcon = () => {
    switch (options.type) {
      case "success":
        return <CheckCircle size={32} className="dialog-icon success" />;
      case "error":
        return <XCircle size={32} className="dialog-icon error" />;
      case "warning":
        return <AlertTriangle size={32} className="dialog-icon warning" />;
      case "confirm":
        return <HelpCircle size={32} className="dialog-icon confirm" />;
      default:
        return <Info size={32} className="dialog-icon info" />;
    }
  };

  const isDeleteConfirm =
    options.destructive ??
    (options.type === "confirm" && options.title.toLowerCase().includes("delete"));

  return (
    <div className="dialog-overlay" role="presentation">
      <div
        className="dialog-box"
        role={options.type === "confirm" ? "alertdialog" : "dialog"}
        aria-modal="true"
        aria-label={options.title}
        tabIndex={-1}
        ref={boxRef}
      >
        <div className="dialog-header">
          {getIcon()}
          <h3 className="dialog-title">{options.title}</h3>
        </div>
        <div className="dialog-body">
          <p className="dialog-message">{options.message}</p>
        </div>
        <div className="dialog-actions">
          {options.type === "confirm" ? (
            <>
              <button className="apple-button secondary" onClick={handleCancel}>
                {options.cancelText || t("dialog.cancel")}
              </button>
              {options.onDeny && (
                <button className="apple-button secondary" onClick={handleDeny}>
                  {options.denyText || t("dialog.dontSave")}
                </button>
              )}
              <button 
                className={`apple-button ${isDeleteConfirm ? "danger" : "primary"}`} 
                onClick={handleConfirm}
              >
                {options.confirmText || t("dialog.confirm")}
              </button>
            </>
          ) : (
            <button className="apple-button primary" onClick={handleConfirm}>
              {options.confirmText || t("dialog.ok")}
            </button>
          )}
        </div>
      </div>

      <style>{`
        .dialog-overlay {
          position: fixed;
          top: 0;
          left: 0;
          width: 100vw;
          height: 100vh;
          background: var(--scrim);
          backdrop-filter: blur(12px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 9999;
          animation: dialogFadeIn 0.12s ease-out;
        }

        .dialog-box {
          background: var(--bg-panel);
          border: 1px solid var(--border-color);
          border-radius: 16px;
          padding: 24px;
          width: 380px;
          max-width: 90%;
          box-shadow: var(--shadow-lg);
          display: flex;
          flex-direction: column;
          gap: 16px;
          animation: dialogScaleUp 0.16s cubic-bezier(0.23, 1, 0.32, 1);
        }

        .dialog-header {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .dialog-icon {
          flex-shrink: 0;
        }

        .dialog-icon.success { color: var(--system-green); }
        .dialog-icon.error { color: var(--system-red); }
        .dialog-icon.warning { color: var(--system-orange); }
        .dialog-icon.confirm { color: var(--system-blue); }
        .dialog-icon.info { color: var(--system-blue); }

        .dialog-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--text-primary);
          letter-spacing: -0.2px;
        }

        .dialog-body {
          color: var(--text-secondary);
          font-size: 13px;
          line-height: 1.5;
          word-break: keep-all;
          white-space: pre-wrap;
        }

        .dialog-actions {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          margin-top: 6px;
        }

        .dialog-actions .apple-button {
          min-width: 80px;
          justify-content: center;
          font-size: 13px;
          padding: 6px 16px;
        }

        .dialog-actions .apple-button.secondary {
          background-color: transparent;
          border: 1px solid var(--border-color);
          color: var(--text-primary);
        }

        .dialog-actions .apple-button.secondary:hover {
          background-color: var(--fill-hover);
        }

        @keyframes dialogFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes dialogScaleUp {
          from { transform: scale(0.95); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
};
