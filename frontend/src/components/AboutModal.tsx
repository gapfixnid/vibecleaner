// frontend/src/components/AboutModal.tsx
// Minimal About dialog: program icon, name, and version.
// NOTE: intentionally minimal for now — to be expanded later (license, links, credits).
import React, { useEffect, useRef } from "react";
import { APP_NAME, APP_VERSION } from "../appMeta";

interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AboutModal: React.FC<AboutModalProps> = ({ isOpen, onClose }) => {
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    boxRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="about-overlay" role="presentation" onClick={onClose}>
      <div
        className="about-box"
        role="dialog"
        aria-modal="true"
        aria-label={`About ${APP_NAME}`}
        tabIndex={-1}
        ref={boxRef}
        onClick={(e) => e.stopPropagation()}
      >
        <img className="about-icon" src="/favicon.svg" alt={`${APP_NAME} icon`} width={72} height={72} />
        <div className="about-name">{APP_NAME}</div>
        <div className="about-version">Version {APP_VERSION}</div>
        <button className="apple-button primary about-ok" onClick={onClose}>
          OK
        </button>
      </div>

      <style>{`
        .about-overlay {
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

        .about-box {
          background: var(--bg-panel);
          border: 1px solid var(--border-color);
          border-radius: 16px;
          padding: 28px 32px;
          width: 300px;
          max-width: 90%;
          box-shadow: var(--shadow-lg);
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 10px;
          text-align: center;
          animation: dialogScaleUp 0.16s cubic-bezier(0.23, 1, 0.32, 1);
        }

        .about-icon {
          border-radius: 16px;
          margin-bottom: 4px;
        }

        .about-name {
          font-size: 18px;
          font-weight: 700;
          color: var(--text-primary);
          letter-spacing: -0.3px;
        }

        .about-version {
          font-size: 12px;
          color: var(--text-secondary);
        }

        .about-ok {
          margin-top: 14px;
          min-width: 90px;
          justify-content: center;
          font-size: 13px;
          padding: 6px 16px;
        }
      `}</style>
    </div>
  );
};
