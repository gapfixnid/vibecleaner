import React from "react";
import { Image, LoaderCircle, Sparkles } from "lucide-react";
import { APP_NAME } from "../appMeta";

interface StartupLoadingScreenProps {
  t: (key: "backend.startingTitle" | "backend.startingDesc") => string;
}

export const StartupLoadingScreen: React.FC<StartupLoadingScreenProps> = ({ t }) => (
  <div className="startup-loading-screen" role="status" aria-live="polite" aria-busy="true">
    <div className="startup-loading-mark" aria-hidden="true">
      <div className="startup-loading-page startup-loading-page-back" />
      <div className="startup-loading-page startup-loading-page-front">
        <Image size={28} strokeWidth={1.5} />
      </div>
      <span className="startup-loading-sparkle">
        <Sparkles size={16} />
      </span>
    </div>
    <p className="startup-loading-brand">{APP_NAME}</p>
    <h1>{t("backend.startingTitle")}</h1>
    <p className="startup-loading-description">{t("backend.startingDesc")}</p>
    <LoaderCircle className="startup-loading-spinner" size={20} aria-hidden="true" />

    <style>{`
      .startup-loading-screen {
        position: fixed;
        inset: 0;
        z-index: 10001;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 32px;
        overflow: hidden;
        color: var(--text-primary);
        text-align: center;
        background:
          radial-gradient(circle at 50% 42%, color-mix(in srgb, var(--system-blue) 11%, transparent), transparent 31%),
          var(--bg-canvas, #1e1e1e);
      }

      .startup-loading-mark {
        position: relative;
        width: 84px;
        height: 92px;
        margin-bottom: 24px;
      }

      .startup-loading-page {
        position: absolute;
        width: 58px;
        height: 76px;
        border: 1px solid var(--border-color);
        border-radius: 10px;
        background: var(--bg-panel);
        box-shadow: var(--shadow-lg);
      }

      .startup-loading-page-back {
        top: 0;
        left: 8px;
        opacity: 0.58;
        transform: rotate(-7deg);
      }

      .startup-loading-page-front {
        right: 5px;
        bottom: 0;
        display: grid;
        place-items: center;
        color: var(--system-blue);
        transform: rotate(4deg);
      }

      .startup-loading-sparkle {
        position: absolute;
        top: 4px;
        right: 0;
        display: grid;
        place-items: center;
        width: 28px;
        height: 28px;
        border: 1px solid color-mix(in srgb, var(--system-blue) 28%, var(--border-color));
        border-radius: 50%;
        color: var(--system-blue);
        background: var(--bg-panel);
        box-shadow: var(--shadow-md);
      }

      .startup-loading-brand {
        margin: 0 0 10px;
        color: var(--system-blue);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
      }

      .startup-loading-screen h1 {
        margin: 0;
        font-size: 20px;
        font-weight: 650;
        letter-spacing: -0.35px;
      }

      .startup-loading-description {
        max-width: 380px;
        margin: 12px 0 22px;
        color: var(--text-secondary);
        font-size: 13px;
        line-height: 1.6;
        word-break: keep-all;
      }

      .startup-loading-spinner {
        color: var(--system-blue);
        animation: startup-loading-spin 0.85s linear infinite;
      }

      @keyframes startup-loading-spin {
        to { transform: rotate(360deg); }
      }

      @media (prefers-reduced-motion: reduce) {
        .startup-loading-spinner { animation-duration: 1.8s; }
      }
    `}</style>
  </div>
);
