// frontend/src/components/StatusBar.tsx
import React, { useEffect, useState } from "react";
import type { Settings } from "../types";

interface StatusBarProps {
  isProcessing: boolean;
  settings: Settings;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  isProcessing,
  settings,
}) => {
  const [dots, setDots] = useState(0);

  useEffect(() => {
    if (!isProcessing) {
      setDots(0);
      return;
    }
    const interval = setInterval(() => {
      setDots((d) => (d + 1) % 4); // 0 → 1 → 2 → 3 → 0
    }, 400);
    return () => clearInterval(interval);
  }, [isProcessing]);

  const dotStr = isProcessing ? ".".repeat(dots) : "";

  return (
    <footer className="statusbar-container">
      <div className="statusbar-left">
        <span className="statusbar-item status-label">
          {isProcessing ? "Working" + dotStr : "Ready"}
        </span>
      </div>

      <div className="statusbar-right">
        {settings.detect_model && (
          <>
            <span className="statusbar-item config-info">
              Detector: {settings.detect_model.includes("High Precision") ? "High Precision" : "Default"}
            </span>
            <div className="statusbar-divider" />
          </>
        )}
        {settings.translation_provider && (
          <span className="statusbar-item config-info">
            Translator: {settings.translation_provider.toUpperCase()}
          </span>
        )}
      </div>

      <style>{`
        .statusbar-container {
          height: var(--statusbar-height, 24px);
          background-color: var(--bg-toolbar);
          backdrop-filter: var(--glass-blur);
          border-top: 1px solid var(--border-color);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 16px;
          z-index: 10;
          user-select: none;
          font-family: var(--font-family);
          font-size: 11px;
          color: var(--text-secondary);
        }

        .statusbar-left, .statusbar-right {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .statusbar-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-weight: 500;
          letter-spacing: -0.1px;
          white-space: nowrap;
        }

        .statusbar-divider {
          width: 1px;
          height: 12px;
          background-color: var(--border-color);
        }

       `}</style>
    </footer>
  );
};
