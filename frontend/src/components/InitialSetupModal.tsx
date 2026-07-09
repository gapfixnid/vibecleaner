import React, { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Download, Loader2 } from "lucide-react";
import { AppleSelect } from "./AppleSelect";
import * as api from "../services/api";
import { createTranslator } from "../i18n";
import type { WaitForJob } from "../hooks/useProcessingTask";
import type { ModelStatus, Settings } from "../types";

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
  const ocrEngine = settings.ocr_engine.toLowerCase();
  const sourceLanguage = settings.source_language.toLowerCase();
  const inpaintEngine = settings.inpaint_engine.toLowerCase();

  appendUnique(
    items,
    detectModel.includes("int8")
      ? { id: "rtdetr-int8-onnx", category: "Detection", label: "RT-DETRv2 INT8" }
      : { id: "rtdetr-v2-onnx", category: "Detection", label: "RT-DETRv2 FP32" },
    installed
  );

  const ppocrRecognition =
    sourceLanguage === "english" || sourceLanguage === "en"
      ? { id: "ppocr-v5-rec-en-mobile", category: "OCR", label: "PP-OCRv5 English Recognition" }
      : sourceLanguage === "korean" || sourceLanguage === "ko"
        ? { id: "ppocr-v5-rec-korean-mobile", category: "OCR", label: "PP-OCRv5 Korean Recognition" }
        : { id: "ppocr-v5-rec-ch-mobile", category: "OCR", label: "PP-OCRv5 Chinese/Japanese Recognition" };

  if (ocrEngine === "fast" || ocrEngine === "ppocr") {
    appendUnique(items, { id: "ppocr-v5-det-mobile", category: "OCR", label: "PP-OCRv5 Mobile Detector" }, installed);
    appendUnique(items, ppocrRecognition, installed);
  } else if (sourceLanguage === "japanese" || sourceLanguage === "ja" || sourceLanguage === "日本語") {
    appendUnique(items, { id: "manga-ocr-mobile-onnx", category: "OCR", label: "Manga OCR Mobile ONNX" }, installed);
  } else {
    appendUnique(items, { id: "ppocr-v5-det-mobile", category: "OCR", label: "PP-OCRv5 Mobile Detector" }, installed);
    appendUnique(items, ppocrRecognition, installed);
  }

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
  const uiT = useMemo(() => createTranslator(localSettings.ui_language), [localSettings.ui_language]);

  useEffect(() => {
    if (!isOpen) return;
    setLocalSettings({ ...settings });
    setError(null);
    setProgressText("");
    setProgressPct(null);
    api.getModelStatus().then(setModelStatus).catch(() => setModelStatus(null));
  }, [isOpen, settings]);

  if (!isOpen) return null;

  const updateLocal = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setLocalSettings((prev) => ({ ...prev, [key]: value }));
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
      <div className="setup-panel">
        <div className="setup-header">
          <div>
            <h1>{uiT("setup.title")}</h1>
            <p>{uiT("setup.subtitle")}</p>
          </div>
        </div>

        <div className="setup-grid">
          <section className="setup-section">
            <div className="setup-section-title">{uiT("setup.languages")}</div>
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
                options={[
                  { value: "Japanese", label: "Japanese" },
                  { value: "Korean", label: "Korean" },
                  { value: "Chinese", label: "Chinese" },
                  { value: "English", label: "English" },
                ]}
              />
            </div>
            <div className="setup-row">
              <label>{uiT("settings.targetLanguage")}</label>
              <AppleSelect
                value={localSettings.target_language}
                onChange={(value) => updateLocal("target_language", value)}
                options={[
                  { value: "Korean", label: "Korean" },
                  { value: "English", label: "English" },
                  { value: "Japanese", label: "Japanese" },
                  { value: "Chinese", label: "Chinese" },
                ]}
              />
            </div>
          </section>

          <section className="setup-section">
            <div className="setup-section-title">{uiT("setup.models")}</div>
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
              <label>{uiT("settings.ocrEngine")}</label>
              <AppleSelect
                value={localSettings.ocr_engine}
                onChange={(value) => updateLocal("ocr_engine", value)}
                options={[
                  { value: "balanced", label: uiT("settings.ocrEngineBalanced") },
                  { value: "fast", label: uiT("settings.ocrEngineFast") },
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
          </section>
        </div>

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
          <button type="button" className="setup-secondary" onClick={completeWithoutDownload} disabled={isWorking}>
            {uiT("setup.skip")}
          </button>
          <button type="button" className="setup-primary" onClick={saveAndDownload} disabled={isWorking}>
            {previewReady ? <CheckCircle2 size={16} /> : <Download size={16} />}
            <span>{previewReady ? uiT("setup.saveAndContinue") : uiT("setup.saveAndDownload")}</span>
          </button>
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
          background: rgba(12, 14, 18, 0.58);
          padding: 24px;
        }
        .setup-panel {
          width: min(860px, 100%);
          max-height: min(760px, calc(100vh - 48px));
          overflow: auto;
          background: var(--panel-bg, #fff);
          color: var(--text-primary, #111827);
          border: 1px solid var(--border-color, rgba(0,0,0,0.12));
          border-radius: 8px;
          box-shadow: 0 24px 80px rgba(0,0,0,0.28);
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
          color: var(--text-secondary, #5b6472);
          font-size: 13px;
        }
        .setup-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 16px;
          margin-top: 22px;
        }
        .setup-section,
        .setup-model-list {
          border: 1px solid var(--border-color, rgba(0,0,0,0.12));
          border-radius: 8px;
          padding: 16px;
          background: var(--surface-bg, rgba(255,255,255,0.6));
        }
        .setup-model-list {
          margin-top: 16px;
        }
        .setup-section-title {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--text-secondary, #5b6472);
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
          border-top: 1px solid var(--border-color, rgba(0,0,0,0.1));
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
          color: var(--text-secondary, #5b6472);
          margin-top: 2px;
        }
        .setup-model-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #b8c0cc;
        }
        .setup-model-dot.ready {
          background: #2f9e44;
        }
        .setup-empty,
        .setup-progress,
        .setup-error {
          font-size: 13px;
          color: var(--text-secondary, #5b6472);
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
          background: var(--fill-2, rgba(0,0,0,0.08));
          overflow: hidden;
        }
        .setup-progress-fill {
          position: absolute;
          top: 0;
          left: 0;
          height: 100%;
          border-radius: 999px;
          background: var(--system-blue, #2563eb);
          transition: width 0.35s ease;
        }
        .setup-progress-pct {
          font-variant-numeric: tabular-nums;
          font-size: 12px;
        }
        .setup-error {
          margin-top: 16px;
          color: #d9480f;
        }
        .setup-spin {
          animation: setup-spin 0.9s linear infinite;
        }
        .setup-actions {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          margin-top: 20px;
        }
        .setup-primary,
        .setup-secondary {
          height: 34px;
          border-radius: 7px;
          border: 1px solid var(--border-color, rgba(0,0,0,0.14));
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
          background: var(--accent-color, #2563eb);
          border-color: var(--accent-color, #2563eb);
        }
        .setup-secondary {
          background: transparent;
          color: var(--text-primary, #111827);
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
          .setup-grid {
            grid-template-columns: 1fr;
          }
          .setup-row {
            grid-template-columns: 1fr;
          }
          .setup-actions {
            flex-direction: column-reverse;
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
