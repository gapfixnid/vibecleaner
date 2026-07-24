import React, { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Download, Loader2 } from "lucide-react";
import { AppleSelect } from "./AppleSelect";
import * as api from "../services/api";
import { createTranslator } from "../i18n";
import type { WaitForJob } from "../hooks/useProcessingTask";
import type { ModelStatus, ProviderCatalogDto, Settings } from "../types";
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

function getCatalogOptions(catalog: ProviderCatalogDto | null, stage: string, key: string) {
  const field = catalog?.providers.find((provider) => provider.stage === stage)
    ?.config_schema.find((item) => item.key === key);
  return field?.choices.map((value, index) => ({
    value,
    label: field.choice_labels[index] || value,
  })) || [];
}

interface SetupTranslationField {
  key: string;
  value_type: "string" | "integer" | "number" | "boolean" | "enum" | "secret" | "model";
  label: string;
  advanced?: boolean;
  placeholder?: string | null;
  visible_when_key?: string | null;
  visible_when_value?: unknown;
}

function getFallbackTranslationFields(provider: string): SetupTranslationField[] {
  const secret = (label: string, placeholder?: string): SetupTranslationField => ({
    key: "translation_api_key",
    value_type: "secret",
    label,
    placeholder,
  });
  const model: SetupTranslationField = {
    key: "translation_model",
    value_type: "model",
    label: "settings.model",
  };
  if (provider === "deepl") return [secret("settings.deeplApiKey", "settings.deeplApiKeyPlaceholder")];
  if (provider === "openai") return [secret("settings.openaiApiKey", "sk-proj-..."), model];
  if (provider === "claude") return [secret("settings.claudeApiKey", "sk-ant-..."), model];
  if (provider === "papago") return [
    { key: "translation_api_base_url", value_type: "string", label: "settings.papagoClientId", placeholder: "settings.papagoClientIdPlaceholder" },
    secret("settings.papagoClientSecret", "settings.papagoClientSecretPlaceholder"),
  ];
  if (provider === "baidu") return [
    { key: "translation_api_base_url", value_type: "string", label: "settings.baiduAppId", placeholder: "settings.baiduAppIdPlaceholder" },
    secret("settings.baiduSecretKey", "settings.baiduSecretKeyPlaceholder"),
  ];
  if (provider === "ollama") return [model];
  if (provider === "openai_compatible") return [
    { key: "translation_api_base_url", value_type: "string", label: "settings.apiBaseUrl", placeholder: "http://localhost:1234/v1" },
    model,
    secret("settings.apiKeyOptional", "settings.optionalApiKeyPlaceholder"),
  ];
  return [];
}

function getSetupModelLabel(value: string, label: string) {
  if (value === "ppocr-v6-medium") return "PP-OCRv6 Medium ONNX";
  if (value === "ppocr-v6-small") return "PP-OCRv6 Small ONNX";
  return label;
}

function getPreviewModels(settings: Settings, status: ModelStatus | null, catalog: ProviderCatalogDto | null): PreviewModel[] {
  const installed = new Set(status?.required.filter((model) => model.downloaded).map((model) => model.id) || []);
  const items: PreviewModel[] = [];
  const detectModel = settings.detect_model.toLowerCase();
  const inpaintEngine = settings.inpaint_engine.toLowerCase();
  const detectionOptions = getCatalogOptions(catalog, "detection", "detect_model");
  const ocrOptions = getCatalogOptions(catalog, "ocr", "ocr_model");
  const inpaintOptions = getCatalogOptions(catalog, "inpainting", "inpaint_engine");

  if (settings.detect_model.startsWith("custom:")) {
    appendUnique(items, {
      id: settings.detect_model,
      category: "Detection",
      label: detectionOptions.find((option) => option.value === settings.detect_model)?.label || settings.detect_model,
    }, new Set([settings.detect_model]));
  } else {
    appendUnique(
      items,
      detectModel.includes("yolo")
        ? { id: "yolo-v8-onnx", category: "Detection", label: "YOLOv8/11 ONNX" }
        : detectModel.includes("int8")
          ? { id: "rtdetr-int8-onnx", category: "Detection", label: "RT-DETRv2 INT8" }
          : { id: "rtdetr-v2-onnx", category: "Detection", label: "RT-DETRv2 FP32" },
      installed
    );
  }

  const useSmallOcr = settings.ocr_model === "ppocr-v6-small";
  const ppocrRecognition = {
    id: useSmallOcr ? "ppocr-v6-rec-small" : "ppocr-v6-rec-medium",
    category: "OCR",
    label: useSmallOcr ? "PP-OCRv6 Small Recognition" : "PP-OCRv6 Medium Recognition",
  };

  if (settings.ocr_model.startsWith("custom:")) {
    appendUnique(items, {
      id: settings.ocr_model,
      category: "OCR",
      label: getSetupModelLabel(
        settings.ocr_model,
        ocrOptions.find((option) => option.value === settings.ocr_model)?.label || settings.ocr_model,
      ),
    }, new Set([settings.ocr_model]));
  } else {
    appendUnique(items, {
      id: useSmallOcr ? "ppocr-v6-det-small" : "ppocr-v6-det-medium",
      category: "OCR",
      label: useSmallOcr ? "PP-OCRv6 Small Detection" : "PP-OCRv6 Medium Detection",
    }, installed);
    appendUnique(items, ppocrRecognition, installed);
  }

  if (settings.inpaint_engine.startsWith("custom:")) {
    appendUnique(items, {
      id: settings.inpaint_engine,
      category: "Inpainting",
      label: inpaintOptions.find((option) => option.value === settings.inpaint_engine)?.label || settings.inpaint_engine,
    }, new Set([settings.inpaint_engine]));
  } else if (inpaintEngine === "aot") {
    appendUnique(items, { id: "aot-onnx", category: "Inpainting", label: "AOT ONNX" }, installed);
  } else {
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
  const [providerCatalog, setProviderCatalog] = useState<ProviderCatalogDto | null>(null);
  const [translationModels, setTranslationModels] = useState<string[]>([]);
  const [translationModelsContext, setTranslationModelsContext] = useState("");
  const [translationModelsLoadingContext, setTranslationModelsLoadingContext] = useState("");
  const [translationModelsError, setTranslationModelsError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);
  const [progressText, setProgressText] = useState("");
  const [progressPct, setProgressPct] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [setupStep, setSetupStep] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const uiT = useMemo(() => createTranslator(localSettings.ui_language), [localSettings.ui_language]);
  const translationProviders = useMemo(() => (providerCatalog?.providers || [])
    .filter((provider) => provider.stage === "translation")
    .sort((left, right) => left.catalog_order - right.catalog_order), [providerCatalog]);
  const selectedTranslationProvider = translationProviders.find(
    (provider) => provider.selection_value === localSettings.translation_provider,
  );
  const translationConfigFields: SetupTranslationField[] = selectedTranslationProvider?.config_schema
    ?? getFallbackTranslationFields(localSettings.translation_provider);
  const providerFeatures = new Set(selectedTranslationProvider?.capabilities.features || []);
  const providerSupportsModelPicker = selectedTranslationProvider
    ? providerFeatures.has("model-picker")
    : ["openai", "claude", "ollama", "openai_compatible"].includes(localSettings.translation_provider);
  const providerNeedsKey = selectedTranslationProvider
    ? providerFeatures.has("model-requires-key")
    : ["openai", "claude"].includes(localSettings.translation_provider);
  const providerSetupHelp = localSettings.translation_provider === "google"
    ? uiT("setup.googleProviderHelp")
    : localSettings.translation_provider === "ollama"
      ? uiT("setup.ollamaProviderHelp")
      : selectedTranslationProvider?.description
        ? uiT(selectedTranslationProvider.description)
        : "";
  const translationModelRequestContext = [
    localSettings.translation_provider,
    localSettings.translation_api_key,
    localSettings.translation_api_base_url,
  ].join("\u0000");
  const visibleTranslationModels = translationModelsContext === translationModelRequestContext
    ? translationModels
    : [];
  const visibleTranslationModelsError = translationModelsContext === translationModelRequestContext
    ? translationModelsError
    : null;
  const translationModelsLoading = translationModelsLoadingContext === translationModelRequestContext;
  useFocusTrap(panelRef, isOpen);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    let retryTimer: number | undefined;
    let attempts = 0;
    const loadStartupData = async () => {
      try {
        const [status, catalog] = await Promise.all([
          api.getModelStatus(),
          api.getProviderCatalog(),
        ]);
        if (!active) return;
        setModelStatus(status);
        setProviderCatalog(catalog);
      } catch {
        if (!active || attempts >= 20) return;
        attempts += 1;
        retryTimer = window.setTimeout(() => void loadStartupData(), 500);
      }
    };
    void loadStartupData();
    return () => {
      active = false;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !providerSupportsModelPicker) return;
    if (providerNeedsKey && !localSettings.translation_api_key) return;

    let active = true;
    const timer = window.setTimeout(async () => {
      setTranslationModelsLoadingContext(translationModelRequestContext);
      try {
        const result = await api.getTranslationModels(
          localSettings.translation_provider,
          localSettings.translation_api_key,
          localSettings.translation_api_base_url,
        );
        if (!active) return;
        setTranslationModelsContext(translationModelRequestContext);
        setTranslationModels(result.models || []);
        setTranslationModelsError(result.error || null);
      } catch {
        if (active) {
          setTranslationModelsContext(translationModelRequestContext);
          setTranslationModels([]);
          setTranslationModelsError(uiT("settings.modelsLoadFailed"));
        }
      } finally {
        if (active) setTranslationModelsLoadingContext("");
      }
    }, 350);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [
    isOpen,
    localSettings.translation_api_base_url,
    localSettings.translation_api_key,
    localSettings.translation_provider,
    providerNeedsKey,
    providerSupportsModelPicker,
    translationModelRequestContext,
    uiT,
  ]);

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
  const previewModels = getPreviewModels(localSettings, modelStatus, providerCatalog);
  const detectionOptions = getCatalogOptions(providerCatalog, "detection", "detect_model");
  const ocrOptions = getCatalogOptions(providerCatalog, "ocr", "ocr_model").map((option) => ({
    ...option,
    label: getSetupModelLabel(option.value, option.label),
  }));
  const inpaintOptions = getCatalogOptions(providerCatalog, "inpainting", "inpaint_engine");
  const recommendedLabel = uiT("settings.recommended");
  const withRecommended = (options: Array<{ value: string; label: string; disabled?: boolean }>, defaultValue: string) =>
    options.map((option) => option.value === defaultValue
      ? { ...option, label: `${option.label} (${recommendedLabel})` }
      : option);
  const visibleDetectionOptions = detectionOptions.length ? detectionOptions : [
      { value: "High Precision (FP32)", label: uiT("settings.modelHighPrecision") },
      { value: "Small (INT8)", label: uiT("settings.modelSmall") },
      { value: "YOLOv8/11 ONNX", label: "YOLOv8/11 ONNX" },
  ];
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
            <div className="setup-row">
              <label>{uiT("settings.translationProvider")}</label>
              <div className="setup-provider-control-line">
                <AppleSelect
                  value={localSettings.translation_provider}
                  onChange={(value) => updateLocal("translation_provider", value)}
                  options={translationProviders.length > 0
                    ? translationProviders.map((provider) => ({
                        value: provider.selection_value,
                        label: provider.display_name,
                      }))
                    : [
                        { value: "google", label: uiT("settings.providerGoogle") },
                        { value: "deepl", label: "DeepL Translation API" },
                        { value: "openai", label: "OpenAI" },
                        { value: "claude", label: "Anthropic Claude" },
                        { value: "papago", label: "Naver Papago API" },
                        { value: "baidu", label: "Baidu Fanyi API" },
                        { value: "ollama", label: uiT("settings.providerOllama") },
                        { value: "openai_compatible", label: uiT("settings.providerCompatible") },
                      ]}
                />
                {providerSetupHelp && <p className="setup-provider-help">{providerSetupHelp}</p>}
              </div>
            </div>
            {translationConfigFields
              .filter((field) => !field.visible_when_key
                || localSettings[field.visible_when_key as keyof Settings] === field.visible_when_value)
              .map((field) => (
                <div className="setup-row setup-provider-row" key={field.key}>
                  <label>{uiT(field.label)}</label>
                  {field.value_type === "model" && visibleTranslationModels.length > 0 ? (
                    <AppleSelect
                      value={localSettings.translation_model}
                      onChange={(value) => updateLocal("translation_model", value)}
                      options={[
                        { value: "", label: uiT("settings.selectModel") },
                        ...visibleTranslationModels.map((model) => ({ value: model, label: model })),
                        ...(localSettings.translation_model
                          && !visibleTranslationModels.includes(localSettings.translation_model)
                          ? [{ value: localSettings.translation_model, label: localSettings.translation_model }]
                          : []),
                      ]}
                    />
                  ) : (
                    <div className="setup-provider-input-wrap">
                      <input
                        type={field.value_type === "secret" ? "password" : "text"}
                        className="setup-provider-input"
                        value={String(localSettings[field.key as keyof Settings] ?? "")}
                        placeholder={field.placeholder ? uiT(field.placeholder) : ""}
                        onChange={(event) => updateLocal(
                          field.key as keyof Settings,
                          event.target.value as Settings[keyof Settings],
                        )}
                      />
                      {field.value_type === "model" && translationModelsLoading && (
                        <span className="setup-field-help">{uiT("settings.loadingModels")}</span>
                      )}
                      {field.value_type === "model" && visibleTranslationModelsError && (
                        <span className="setup-field-help error">{visibleTranslationModelsError}</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
          </section>}

          {setupStep === 1 && <section className="setup-section">
            <div className="setup-section-title">{uiT("setup.models")}</div>
            <p className="setup-stage-help">{uiT("setup.profileHelp")}</p>
            <div className="setup-row">
              <label>{uiT("settings.detectionModel")}</label>
              <AppleSelect
                value={localSettings.detect_model}
                onChange={(value) => updateLocal("detect_model", value)}
                options={withRecommended(visibleDetectionOptions, "High Precision (FP32)")}
              />
            </div>
            <div className="setup-row">
              <label>{uiT("settings.ocrModel")}</label>
              <AppleSelect
                value={localSettings.ocr_model}
                onChange={(value) => updateLocal("ocr_model", value)}
                options={withRecommended(ocrOptions.length ? ocrOptions : [
                  { value: "ppocr-v6-medium", label: "PP-OCRv6 Medium ONNX" },
                  { value: "ppocr-v6-small", label: "PP-OCRv6 Small ONNX" },
                ], "ppocr-v6-medium")}
              />
            </div>
            <div className="setup-row">
              <label>{uiT("settings.inpaintingEngine")}</label>
              <AppleSelect
                value={localSettings.inpaint_engine}
                onChange={(value) => updateLocal("inpaint_engine", value)}
                options={withRecommended(inpaintOptions.length ? inpaintOptions : [
                  { value: "aot", label: uiT("settings.inpaintingEngineAot") },
                  { value: "lama", label: uiT("settings.inpaintingEngineBalanced") },
                ], "aot")}
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
        .setup-provider-control-line {
          display: grid;
          grid-template-columns: 250px minmax(0, 1fr);
          align-items: center;
          gap: 12px;
        }
        .setup-provider-help {
          margin: 0;
          color: var(--text-secondary);
          font-size: 11px;
          line-height: 1.35;
          white-space: nowrap;
        }
        .setup-provider-input-wrap {
          display: flex;
          flex-direction: column;
          gap: 5px;
        }
        .setup-provider-input {
          width: 100%;
          height: 30px;
          box-sizing: border-box;
          border: 1px solid var(--border-color);
          border-radius: 6px;
          padding: 0 8px;
          background: var(--bg-input);
          color: var(--text-primary);
          font-family: var(--font-family);
          font-size: 11.5px;
          font-weight: 400;
          outline: none;
        }
        .setup-provider-input::placeholder {
          color: var(--text-tertiary);
          font-size: 11px;
          opacity: 0.8;
        }
        .setup-provider-input:focus {
          border-color: var(--border-focus);
          box-shadow: var(--focus-ring-shadow);
        }
        .setup-field-help {
          color: var(--text-secondary);
          font-size: 10.5px;
          line-height: 1.35;
        }
        .setup-field-help.error {
          color: var(--system-red);
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
          .setup-provider-help {
            white-space: normal;
          }
          .setup-provider-control-line {
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
