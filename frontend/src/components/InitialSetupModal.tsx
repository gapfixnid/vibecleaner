import React, { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Download, Loader2 } from "lucide-react";
import { AppleSelect } from "./AppleSelect";
import * as api from "../services/api";
import { createTranslator } from "../i18n";
import type { WaitForJob } from "../hooks/useProcessingTask";
import type { ModelStatus, Settings } from "../types";
import { getSafeTargetLanguage, getTargetLanguageOptions, SUPPORTED_TRANSLATION_LANGUAGES } from "../languageOptions";
import { useFocusTrap } from "../hooks/useFocusTrap";

interface InitialSetupModalProps {
  isOpen: boolean;
  settings: Settings;
  onComplete: (settings: Settings) => void;
  /** Shared job poller (timeout + unmount guard) from useProcessingTask. */
  waitForJob: WaitForJob;
}

interface PreviewModel {
  id: string;
  category: string;
  label: string;
  downloaded: boolean;
}

function appendUnique(items: PreviewModel[], item: Omit<PreviewModel, "downloaded">, installed: Set<string>) {
  if (items.some((existing) => existing.id === item.id)) return;
  items.push({ ...item, downloaded: installed.has(item.id) });
}

function getPreviewModels(settings: Settings, status: ModelStatus | null): PreviewModel[] {
  const installed = new Set(status?.required.filter((model) => model.downloaded).map((model) => model.id) || []);
  const items: PreviewModel[] = [];
  const detectModel = settings.detect_model.toLowerCase();
  const inpaintEngine = settings.inpaint_engine.toLowerCase();

  appendUnique(
    items,
    detectModel.includes("int8")
      ? { id: "rtdetr-int8-onnx", category: "Detection", label: "RT-DETRv2 INT8" }
      : { id: "rtdetr-v2-onnx", category: "Detection", label: "RT-DETRv2 FP32" },
    installed
  );

  const ppocrRecognition = {
    id: "ppocr-v6-rec-medium",
    category: "OCR",
    label: "PP-OCRv6 Medium Recognition",
  };

  appendUnique(items, { id: "ppocr-v6-det-medium", category: "OCR", label: "PP-OCRv6 Medium Detection" }, installed);
  appendUnique(items, ppocrRecognition, installed);

  if (inpaintEngine !== "opencv") {
    appendUnique(items, { id: "lama-manga-dynamic", category: "Inpainting", label: "LaMa Manga ONNX" }, installed);
  }

  return items;
}

export const InitialSetupModal: React.FC<InitialSetupModalProps> = ({
  isOpen,
  settings,
  onComplete,
  waitForJob,
}) => {
  const [localSettings, setLocalSettings] = useState<Settings>({ ...settings });
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [isWorking, setIsWorking] = useState(false);
  const [progressText, setProgressText] = useState("");
  const [progressPct, setProgressPct] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [setupStep, setSetupStep] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const uiT = useMemo(() => createTranslator(localSettings.ui_language), [localSettings.ui_language]);
  useFocusTrap(panelRef, isOpen);

  useEffect(() => {
    if (!isOpen) return;
    api.getModelStatus().then(setModelStatus).catch(() => setModelStatus(null));
  }, [isOpen]);

  if (!isOpen) return null;

  const updateLocal = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setLocalSettings((prev) => key === "source_language"
      ? {
          ...prev,
          source_language: value as Settings["source_language"],
          target_language: getSafeTargetLanguage(String(value), prev.target_language),
        }
      : { ...prev, [key]: value });
  };
  const previewModels = getPreviewModels(localSettings, modelStatus);
  const previewReady = previewModels.length > 0 && previewModels.every((model) => model.downloaded);

  const completeWithoutDownload = async () => {
    setIsWorking(true);
    setError(null);
    try {
      const saved = await api.updateSettings({ ...localSettings, setup_completed: true });
      onComplete(saved);
    } catch (e) {
      console.error("Initial setup skip failed", e);
      setError(uiT("setup.saveFailed"));
    } finally {
      setIsWorking(false);
    }
  };

  const saveAndDownload = async () => {
    setIsWorking(true);
    setError(null);
    setProgressText(uiT("setup.saving"));
    try {
      await api.updateSettings({ ...localSettings, setup_completed: false });
      const beforeDownload = await api.getModelStatus();
      setModelStatus(beforeDownload);

      if (!beforeDownload.all_ready) {
        setProgressText(uiT("setup.downloading"));
        const job = await api.downloadRequiredModels();
        // Shared poller throws on failure/cancel; progress drives the bar below.
        await waitForJob(job, uiT("setup.downloadingModels"), {
          onProgress: (latest) => {
            setProgressPct(typeof latest.progress === "number" ? latest.progress : null);
            setProgressText(latest.message || uiT("setup.downloading"));
          },
        });
      }

      const saved = await api.updateSettings({ ...localSettings, setup_completed: true });
      const afterDownload = await api.getModelStatus();
      setModelStatus(afterDownload);
      setProgressPct(null);
      setProgressText(uiT("setup.ready"));
      onComplete(saved);
    } catch (e) {
      console.error("Initial setup download failed", e);
      setError(uiT("setup.downloadFailed"));
      setProgressText("");
      setProgressPct(null);
    } finally {
      setIsWorking(false);
    }
  };

  return (
    <div className="setup-overlay" role="dialog" aria-modal="true" aria-label={uiT("setup.title")}>
      <div className="setup-panel" ref={panelRef} tabIndex={-1}>
        <div className="setup-header">
          <div>
            <h1>{uiT("setup.title")}</h1>
            <p>{uiT("setup.subtitle")}</p>
          </div>
        </div>

        <ol className="setup-stepper" aria-label={uiT("setup.title")}>
          {[uiT("setup.languages"), uiT("setup.models"), uiT("setup.requiredModels")].map((label, index) => (
            <li key={label} className={index < setupStep ? "complete" : index === setupStep ? "active" : ""} aria-current={index === setupStep ? "step" : undefined}>
              <span className="setup-step-number">{index < setupStep ? <CheckCircle2 size={14} /> : index + 1}</span>
              <span>{label}</span>
            </li>
          ))}
        </ol>

        <div className="setup-stage">
          {setupStep === 0 && <section className="setup-section">
            <div className="setup-section-title">{uiT("setup.languages")}</div>
            <p className="setup-stage-help">{uiT("setup.languageHelp")}</p>
            <div className="setup-row">
              <label>{uiT("settings.uiLanguage")}</label>
              <AppleSelect
                value={localSettings.ui_language}
                onChange={(value) => updateLocal("ui_language", value)}
                options={[
                  { value: "en", label: "English" },
                  { value: "ko", label: "한국어" },
                ]}
              />
            </div>
            <div className="setup-row">
              <label>{uiT("settings.sourceLanguage")}</label>
              <AppleSelect
                value={localSettings.source_language}
                onChange={(value) => updateLocal("source_language", value)}
                options={[...SUPPORTED_TRANSLATION_LANGUAGES]}
              />
            </div>
            <div className="setup-row">
              <label>{uiT("settings.targetLanguage")}</label>
              <AppleSelect
                value={localSettings.target_language}
                onChange={(value) => updateLocal("target_language", value)}
                options={[...getTargetLanguageOptions(localSettings.source_language)]}
              />
            </div>
          </section>}

          {setupStep === 1 && <section className="setup-section">
            <div className="setup-section-title">{uiT("setup.models")}</div>
            <p className="setup-stage-help">{uiT("setup.profileHelp")}</p>
            <div className="setup-row">
              <label>{uiT("settings.detectionModel")}</label>
              <AppleSelect
                value={localSettings.detect_model}
                onChange={(value) => updateLocal("detect_model", value)}
                options={[
                  { value: "High Precision (FP32)", label: uiT("settings.modelHighPrecision") },
                  { value: "Small (INT8)", label: uiT("settings.modelSmall") },
                ]}
              />
            </div>
            <div className="setup-row">
              <label>{uiT("settings.inpaintingEngine")}</label>
              <AppleSelect
                value={localSettings.inpaint_engine}
                onChange={(value) => updateLocal("inpaint_engine", value)}
                options={[
                  { value: "lama", label: uiT("settings.inpaintingEngineBalanced") },
                  { value: "opencv", label: uiT("settings.inpaintingEngineFast") },
                ]}
              />
            </div>
          </section>}

          {setupStep === 2 && <>
            <p className="setup-stage-help setup-review-help">{uiT("setup.reviewHelp")}</p>
            <section className="setup-model-list">
              <div className="setup-section-title">{uiT("setup.requiredModels")}</div>
              {previewModels.length ? (
                previewModels.map((model) => (
                  <div className="setup-model-item" key={model.id}>
                    <span className={`setup-model-dot ${model.downloaded ? "ready" : ""}`} />
                    <div>
                      <strong>{model.label}</strong>
                      <span>{model.category}</span>
                    </div>
                    <span>{model.downloaded ? uiT("setup.installed") : uiT("setup.required")}</span>
                  </div>
                ))
              ) : (
                <div className="setup-empty">{uiT("setup.modelsWillBeChecked")}</div>
              )}
            </section>
          </>}
        </div>

        {progressText && (
          <div className="setup-progress">
            <Loader2 size={14} className={isWorking ? "setup-spin" : ""} />
            <span>{progressText}</span>
            {isWorking && progressPct !== null && (
              <>
                <span className="setup-progress-track" aria-hidden="true">
                  <span
                    className="setup-progress-fill"
                    style={{ width: `${Math.max(2, Math.min(100, progressPct))}%` }}
                  />
                </span>
                <span className="setup-progress-pct">{Math.round(progressPct)}%</span>
              </>
            )}
          </div>
        )}
        {error && <div className="setup-error">{error}</div>}

        <div className="setup-actions">
          <div>
            {setupStep > 0 && (
              <button type="button" className="setup-secondary" onClick={() => setSetupStep((step) => step - 1)} disabled={isWorking}>
                {uiT("setup.back")}
              </button>
            )}
          </div>
          <div>
            {setupStep < 2 ? (
              <button type="button" className="setup-primary" onClick={() => setSetupStep((step) => step + 1)}>
                <span>{uiT("setup.continue")}</span>
              </button>
            ) : (
              <>
                <button type="button" className="setup-secondary" onClick={completeWithoutDownload} disabled={isWorking}>
                  {uiT("setup.skip")}
                </button>
                <button type="button" className="setup-primary" onClick={saveAndDownload} disabled={isWorking}>
                  {previewReady ? <CheckCircle2 size={16} /> : <Download size={16} />}
                  <span>{previewReady ? uiT("setup.saveAndContinue") : uiT("setup.saveAndDownload")}</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      <style>{`
        .setup-overlay {
          position: fixed;
          inset: 0;
          z-index: 4000;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--scrim);
          padding: 24px;
        }
        .setup-panel {
          width: min(860px, 100%);
          max-height: min(760px, calc(100vh - 48px));
          overflow: auto;
          background: var(--bg-panel);
          color: var(--text-primary);
          border: 1px solid var(--border-color);
          border-radius: 8px;
          box-shadow: var(--shadow-lg);
          padding: 24px;
        }
        .setup-header h1 {
          margin: 0 0 8px;
          font-size: 24px;
          line-height: 1.2;
          letter-spacing: 0;
        }
        .setup-header p {
          margin: 0;
          color: var(--text-secondary);
          font-size: 13px;
        }
        .setup-stepper {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          margin: 24px 0 20px;
          padding: 0;
          list-style: none;
        }
        .setup-stepper li {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          color: var(--text-tertiary);
          font-size: 11.5px;
          font-weight: 600;
        }
        .setup-stepper li:not(:last-child)::after {
          content: "";
          position: absolute;
          top: 50%;
          left: calc(50% + 58px);
          right: calc(-50% + 58px);
          height: 1px;
          background: var(--separator-strong);
        }
        .setup-stepper li.active {
          color: var(--text-primary);
        }
        .setup-stepper li.complete {
          color: var(--system-green);
        }
        .setup-step-number {
          width: 23px;
          height: 23px;
          display: grid;
          place-items: center;
          border: 1px solid var(--separator-strong);
          border-radius: var(--radius-full);
          background: var(--bg-panel);
          font-size: 10px;
          font-variant-numeric: tabular-nums;
          z-index: 1;
        }
        .setup-stepper li.active .setup-step-number {
          border-color: var(--system-blue);
          background: var(--accent-bg-subtle);
          color: var(--system-blue);
        }
        .setup-stage {
          min-height: 294px;
        }
        .setup-stage-help {
          margin: -2px 0 12px;
          color: var(--text-secondary);
          font-size: 12px;
          line-height: 1.5;
        }
        .setup-section,
        .setup-model-list {
          border: 1px solid var(--border-color);
          border-radius: 8px;
          padding: 16px;
          background: var(--fill-4);
        }
        .setup-model-list {
          margin-top: 0;
        }
        .setup-section-title {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--text-secondary);
          margin-bottom: 12px;
        }
        .setup-row {
          display: grid;
          grid-template-columns: minmax(120px, 0.45fr) minmax(180px, 1fr);
          align-items: center;
          gap: 12px;
          min-height: 42px;
        }
        .setup-row + .setup-row {
          margin-top: 10px;
        }
        .setup-row label {
          font-size: 13px;
          font-weight: 600;
        }
        .setup-model-item {
          display: grid;
          grid-template-columns: 10px minmax(0, 1fr) auto;
          align-items: center;
          gap: 12px;
          min-height: 42px;
          font-size: 12px;
        }
        .setup-model-item + .setup-model-item {
          border-top: 1px solid var(--separator);
        }
        .setup-model-item strong,
        .setup-model-item span {
          display: block;
        }
        .setup-model-item strong {
          font-size: 13px;
          font-weight: 650;
        }
        .setup-model-item div span {
          color: var(--text-secondary);
          margin-top: 2px;
        }
        .setup-model-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--text-quaternary);
        }
        .setup-model-dot.ready {
          background: var(--system-green);
        }
        .setup-empty,
        .setup-progress,
        .setup-error {
          font-size: 13px;
          color: var(--text-secondary);
        }
        .setup-progress {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 16px;
        }
        .setup-progress-track {
          position: relative;
          flex: 1;
          max-width: 220px;
          height: 5px;
          border-radius: 999px;
          background: var(--fill-2);
          overflow: hidden;
        }
        .setup-progress-fill {
          position: absolute;
          top: 0;
          left: 0;
          height: 100%;
          border-radius: 999px;
          background: var(--system-blue);
          transition: width 0.35s ease;
        }
        .setup-progress-pct {
          font-variant-numeric: tabular-nums;
          font-size: 12px;
        }
        .setup-error {
          margin-top: 16px;
          color: var(--system-red);
        }
        .setup-spin {
          animation: setup-spin 0.9s linear infinite;
        }
        .setup-actions {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          margin-top: 20px;
        }
        .setup-actions > div {
          display: flex;
          gap: 8px;
        }
        .setup-primary,
        .setup-secondary {
          height: 34px;
          border-radius: 7px;
          border: 1px solid var(--border-color);
          padding: 0 14px;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 650;
          cursor: pointer;
        }
        .setup-primary {
          color: #fff;
          background: var(--system-blue);
          border-color: var(--system-blue);
        }
        .setup-secondary {
          background: transparent;
          color: var(--text-primary);
        }
        .setup-primary:disabled,
        .setup-secondary:disabled {
          opacity: 0.58;
          cursor: default;
        }
        @keyframes setup-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @media (max-width: 760px) {
          .setup-row {
            grid-template-columns: 1fr;
          }
          .setup-actions {
            gap: 8px;
          }
          .setup-primary,
          .setup-secondary {
            width: 100%;
            justify-content: center;
          }
        }
      `}</style>
    </div>
  );
};
