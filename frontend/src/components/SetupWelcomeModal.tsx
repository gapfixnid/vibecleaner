import React from "react";
import { ArrowRight, Image, Sparkles } from "lucide-react";

interface SetupWelcomeModalProps {
  isOpen: boolean;
  t: (key: "setup.welcomeTitle" | "setup.welcomeDescription" | "setup.welcomeStepOne" | "setup.welcomeStepTwo" | "setup.welcomeStepThree" | "setup.start") => string;
  onStart: () => void;
}

export const SetupWelcomeModal: React.FC<SetupWelcomeModalProps> = ({ isOpen, t, onStart }) => {
  if (!isOpen) return null;
  return (
    <div className="setup-welcome-overlay" role="dialog" aria-modal="true" aria-labelledby="setup-welcome-title">
      <div className="setup-welcome-panel">
        <div className="setup-welcome-icon" aria-hidden="true"><Image size={24} /><Sparkles size={13} /></div>
        <h1 id="setup-welcome-title">{t("setup.welcomeTitle")}</h1>
        <p className="setup-welcome-description">{t("setup.welcomeDescription")}</p>
        <ol className="setup-welcome-list">
          <li>{t("setup.welcomeStepOne")}</li>
          <li>{t("setup.welcomeStepTwo")}</li>
          <li>{t("setup.welcomeStepThree")}</li>
        </ol>
        <div className="setup-welcome-actions">
          <button type="button" className="setup-welcome-primary" onClick={onStart}>
            {t("setup.start")} <ArrowRight size={16} aria-hidden="true" />
          </button>
        </div>
      </div>
      <style>{`
        .setup-welcome-overlay { position: fixed; inset: 0; z-index: 4100; display: grid; place-items: center; padding: 24px; background: var(--scrim); }
        .setup-welcome-panel { width: min(860px, 100%); max-height: min(760px, calc(100vh - 48px)); overflow: auto; padding: 24px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-panel); color: var(--text-primary); box-shadow: var(--shadow-lg); }
        .setup-welcome-icon { position: relative; display: grid; place-items: center; width: 42px; height: 42px; margin-bottom: 16px; border-radius: 8px; color: var(--system-blue); background: var(--accent-bg-subtle); }
        .setup-welcome-icon svg:last-child { position: absolute; right: 6px; top: 5px; }
        .setup-welcome-panel h1 { margin: 0 0 8px; font-size: 24px; line-height: 1.2; letter-spacing: 0; }
        .setup-welcome-description { margin: 0; color: var(--text-secondary); line-height: 1.5; font-size: 13px; }
        .setup-welcome-list { display: grid; gap: 10px; margin: 24px 0 0; padding: 16px 16px 16px 34px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--fill-4); color: var(--text-primary); font-size: 13px; line-height: 1.5; }
        .setup-welcome-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
        .setup-welcome-primary { height: 34px; display: inline-flex; align-items: center; gap: 8px; border: 1px solid var(--system-blue); border-radius: 7px; padding: 0 14px; color: #fff; background: var(--system-blue); font-size: 13px; font-weight: 650; cursor: pointer; }
      `}</style>
    </div>
  );
};
