// frontend/src/components/SettingsModal.tsx
import React, { useEffect, useState, useRef } from "react";
import { AppleSelect } from "./AppleSelect";
import { 
  X, 
  RefreshCw, 
  Sliders, 
  Languages, 
  Scan, 
  Eraser,
  HelpCircle,
} from "lucide-react";
import * as api from "../services/api";
import {
  LLM_TRANSLATION_PROVIDERS,
  getTranslationProviderCapabilities,
} from "../translationSettings";
import type { Settings } from "../types";
import type { ProviderCatalogDto, ProviderConfigFieldDto, ProviderManifestDto } from "../types";
import type { ThemeMeta } from "../themes";
import { NumberStepper } from "./NumberStepper";
import { getSafeTargetLanguage, getTargetLanguageOptions, SUPPORTED_TRANSLATION_LANGUAGES } from "../languageOptions";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: Settings;
  onSave: (updated: Settings) => void;
  backendUrl: string;
  theme: string;
  setTheme: (id: string) => void;
  themes: ThemeMeta[];
  t?: (key: string) => string;
}

type TabType = "general" | "translation" | "detection" | "inpainting";

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onSave,
  theme,
  setTheme,
  themes,
  t = (key) => key,
}) => {
  const [localSettings, setLocalSettings] = useState<Settings>({ ...settings });
  const [providerModels, setProviderModels] = useState<string[]>([]);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [providerCatalog, setProviderCatalog] = useState<ProviderCatalogDto | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("general");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const LLM_PROVIDERS: string[] = [...LLM_TRANSLATION_PROVIDERS];
  const translationProviderManifests = (providerCatalog?.providers || [])
    .filter((provider) => provider.stage === "translation")
    .sort((left, right) => left.catalog_order - right.catalog_order);
  const selectedTranslationManifest = translationProviderManifests.find(
    (provider) => provider.selection_value === localSettings.translation_provider
  );
  const detectionManifest = providerCatalog?.providers.find((provider) => provider.stage === "detection");
  const ocrManifest = providerCatalog?.providers.find((provider) => provider.stage === "ocr");
  const inpaintingManifest = providerCatalog?.providers.find((provider) => provider.stage === "inpainting");
  const selectedFeatures = new Set(selectedTranslationManifest?.capabilities.features || []);
  const fallbackCapabilities = getTranslationProviderCapabilities(localSettings.translation_provider);
  const providerCapabilities = selectedTranslationManifest ? {
    llmOptions: selectedFeatures.has("llm-options"),
    modelPicker: selectedFeatures.has("model-picker"),
    visionContext: selectedFeatures.has("vision-context"),
    systemPrompt: selectedFeatures.has("system-prompt"),
  } : fallbackCapabilities;
  const manifestForSelection = (selection: string) => translationProviderManifests.find(
    (provider) => provider.selection_value === selection
  );
  const providerSupportsModelPicker = (selection: string) => {
    const manifest = manifestForSelection(selection);
    return manifest ? manifest.capabilities.features.includes("model-picker") : LLM_PROVIDERS.includes(selection);
  };
  const providerNeedsKey = (selection: string) => {
    const manifest = manifestForSelection(selection);
    return manifest
      ? manifest.capabilities.features.includes("model-requires-key")
      : selection === "openai" || selection === "claude";
  };

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    api.getProviderCatalog()
      .then((catalog) => {
        if (active) setProviderCatalog(catalog);
      })
      .catch((error) => {
        console.warn("Failed to load provider catalog; using compatibility settings UI", error);
        if (active) setProviderCatalog(null);
      });
    return () => {
      active = false;
    };
  }, [isOpen]);

  // Fetch the live model list for the current LLM provider using the entered
  // credentials. Doubles as API-key validation.
  const fetchProviderModels = async (settingsOverride?: Settings) => {
    const effectiveSettings = settingsOverride || localSettings;
    const provider = effectiveSettings.translation_provider;
    if (!providerSupportsModelPicker(provider)) {
      setProviderModels([]);
      setModelsError(null);
      return;
    }
    if (providerNeedsKey(provider) && !effectiveSettings.translation_api_key) {
      setProviderModels([]);
      setModelsError(null);
      return;
    }
    setIsLoadingModels(true);
    setModelsError(null);
    try {
      const res = await api.getTranslationModels(
        provider,
        effectiveSettings.translation_api_key,
        effectiveSettings.translation_api_base_url
      );
      setProviderModels(res.models || []);
      setModelsError(res.error || null);
    } catch (e) {
      console.warn("Failed to fetch provider models", e);
      setProviderModels([]);
      setModelsError(t("settings.modelsLoadFailed"));
    } finally {
      setIsLoadingModels(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (isOpen && providerSupportsModelPicker(localSettings.translation_provider)) {
        fetchProviderModels();
      } else {
        setProviderModels([]);
        setModelsError(null);
      }
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, localSettings.translation_provider, providerCatalog]);

  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    contentRef.current?.focus();
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

  const handleChange = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setLocalSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleAutoSave = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    const updated = {
      ...localSettings,
      ...(key === "source_language"
        ? {
            source_language: value as Settings["source_language"],
            target_language: getSafeTargetLanguage(String(value), localSettings.target_language),
          }
        : { [key]: value }),
    };
    setLocalSettings(updated);
    onSave(updated);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.currentTarget.blur();
    }
  };

  const renderRangeControl = (
    key: keyof Settings,
    label: string,
    value: number,
    min: number,
    max: number,
    step: number,
    formatValue: (value: number) => string = (v) => String(v),
  ) => (
    <div className="form-row-group stack">
      <div className="flex-space-between">
        <label className="pref-label">{label}</label>
        <span className="pref-value-pill">{formatValue(value)}</span>
      </div>
      <input
        type="range"
        className="pref-range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => handleAutoSave(key, Number(e.target.value))}
      />
    </div>
  );

  // Shared model picker for LLM providers: shows the live model list once
  // available, with loading / error / key-needed states. When allowManual is
  // true (OpenAI-Compatible) and no models are returned, falls back to a free
  // text model field.
  const renderModelSelector = (allowManual = false) => {
    const provider = localSettings.translation_provider;
    const needsKey = providerNeedsKey(provider);
    return (
      <div className="form-row-group stack">
        <div className="flex-space-between">
          <label className="pref-label">{t("settings.model")}</label>
          <button type="button" className="refresh-btn" onClick={() => fetchProviderModels()} disabled={isLoadingModels}>
            <RefreshCw size={11} className={isLoadingModels ? "spin" : ""} />
            <span>{t("settings.refresh")}</span>
          </button>
        </div>
        {needsKey && !localSettings.translation_api_key ? (
          <p className="model-hint">{t("settings.enterApiKeyToLoadModels")}</p>
        ) : isLoadingModels ? (
          <p className="model-hint">{t("settings.loadingModels")}</p>
        ) : modelsError ? (
          <p className="model-error">{modelsError}</p>
        ) : providerModels.length > 0 ? (
          <AppleSelect
            value={localSettings.translation_model}
            onChange={(v) => handleAutoSave("translation_model", v)}
            options={[
              { value: "", label: t("settings.selectModel") },
              ...providerModels.map((m) => ({ value: m, label: m })),
              ...(localSettings.translation_model && !providerModels.includes(localSettings.translation_model)
                ? [{ value: localSettings.translation_model, label: `${localSettings.translation_model} (saved)` }]
                : []),
            ]}
          />
        ) : allowManual ? (
          <input
            type="text"
            className="apple-input-text full text-left"
            placeholder="e.g. llama-3.1-8b-instruct"
            value={localSettings.translation_model}
            onChange={(e) => handleChange("translation_model", e.target.value)}
            onBlur={() => onSave(localSettings)}
            onKeyDown={handleKeyDown}
          />
        ) : (
          <p className="model-hint">{t("settings.noModelsFound")}</p>
        )}
      </div>
    );
  };

  const catalogText = (value: string | null | undefined) => {
    if (!value) return "";
    return value.startsWith("settings.") ? t(value) : value;
  };

  const updateCatalogSetting = (field: ProviderConfigFieldDto, value: string | number | boolean, save: boolean) => {
    if (!(field.key in localSettings)) {
      console.warn(`Provider catalog field is not a known setting: ${field.key}`);
      return;
    }
    const updated = { ...localSettings, [field.key]: value } as Settings;
    setLocalSettings(updated);
    if (save) {
      onSave(updated);
      if (
        selectedFeatures.has("model-picker")
        && (field.value_type === "secret" || field.key === "translation_api_base_url")
      ) {
        fetchProviderModels(updated);
      }
    }
  };

  const renderCatalogField = (field: ProviderConfigFieldDto) => {
    if (
      field.visible_when_key
      && localSettings[field.visible_when_key as keyof Settings] !== field.visible_when_value
    ) {
      return null;
    }
    if (field.value_type === "model") {
      return (
        <React.Fragment key={field.key}>
          {renderModelSelector(selectedFeatures.has("manual-model"))}
        </React.Fragment>
      );
    }

    const value = localSettings[field.key as keyof Settings];
    if (field.value_type === "boolean") {
      return (
        <div className="form-row-group checkbox-row" key={field.key}>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={Boolean(value)}
              onChange={(event) => updateCatalogSetting(field, event.target.checked, true)}
            />
            <span>{catalogText(field.label)}</span>
          </label>
        </div>
      );
    }

    if (field.value_type === "enum") {
      return (
        <div className="form-row-group" key={field.key}>
          <label className="pref-label">{catalogText(field.label)}</label>
          <div className="pref-control-right">
            <AppleSelect
              value={String(value ?? "")}
              onChange={(next) => updateCatalogSetting(field, next, true)}
              options={field.choices.map((choice, index) => ({
                value: choice,
                label: catalogText(field.choice_labels[index] || choice),
              }))}
            />
          </div>
        </div>
      );
    }

    if (
      field.value_type === "integer"
      && field.minimum !== null
      && field.maximum !== null
    ) {
      return (
        <div className="form-row-group" key={field.key}>
          <label className="pref-label">{catalogText(field.label)}</label>
          <div className="pref-control-right">
            <NumberStepper
              label={catalogText(field.label)}
              value={Number(value ?? field.default ?? 0)}
              min={field.minimum}
              max={field.maximum}
              step={field.step ?? 1}
              onChange={(next) => updateCatalogSetting(field, next, true)}
            />
          </div>
        </div>
      );
    }

    const numeric = field.value_type === "integer" || field.value_type === "number";
    return (
      <div className="form-row-group stack" key={field.key}>
        <label className="pref-label">{catalogText(field.label)}</label>
        <input
          type={field.value_type === "secret" ? "password" : numeric ? "number" : "text"}
          className="apple-input-text full text-left"
          min={field.minimum ?? undefined}
          max={field.maximum ?? undefined}
          step={field.step ?? undefined}
          placeholder={catalogText(field.placeholder)}
          value={String(value ?? "")}
          onChange={(event) => updateCatalogSetting(
            field,
            numeric ? Number(event.target.value) : event.target.value,
            false,
          )}
          onBlur={(event) => updateCatalogSetting(
            field,
            numeric ? Number(event.target.value) : event.target.value,
            true,
          )}
          onKeyDown={handleKeyDown}
        />
        {field.help_text && <span className="pref-help-text">{catalogText(field.help_text)}</span>}
      </div>
    );
  };

  const renderCatalogProviderConfig = (manifest: ProviderManifestDto) => (
    <>
      {manifest.description && (
        <div className="provider-info-block">
          <HelpCircle className="info-icon" size={16} />
          <p>{catalogText(manifest.description)}</p>
        </div>
      )}
      {manifest.config_schema.map(renderCatalogField)}
    </>
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  };

  const toggleAdvanced = () => {
    setShowAdvanced((current) => {
      const next = !current;
      if (!next && (activeTab === "detection" || activeTab === "inpainting")) {
        setActiveTab("general");
      }
      return next;
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={t("toolbar.settings")}
        tabIndex={-1}
        ref={contentRef}
      >
        
        {/* Left Category Sidebar */}
        <div className="preferences-sidebar">
          <div className="sidebar-header-pref">
            <h3>{t("settings.preferences")}</h3>
          </div>
          <div className="sidebar-menu-pref">
            <button
              type="button" 
              className={`menu-btn-pref ${activeTab === "general" ? "active" : ""}`}
              onClick={() => setActiveTab("general")}
            >
              <div className="btn-icon-wrapper general">
                <Sliders size={14} />
              </div>
              <span>{t("settings.general")}</span>
            </button>
            <button
              type="button" 
              className={`menu-btn-pref ${activeTab === "translation" ? "active" : ""}`}
              onClick={() => setActiveTab("translation")}
            >
              <div className="btn-icon-wrapper translation">
                <Languages size={14} />
              </div>
              <span>{t("settings.translation")}</span>
            </button>
            {showAdvanced && <button
              type="button" 
              className={`menu-btn-pref ${activeTab === "detection" ? "active" : ""}`}
              onClick={() => setActiveTab("detection")}
            >
              <div className="btn-icon-wrapper detection">
                <Scan size={14} />
              </div>
              <span>{t("settings.detection")}</span>
            </button>}
            {showAdvanced && <button
              type="button" 
              className={`menu-btn-pref ${activeTab === "inpainting" ? "active" : ""}`}
              onClick={() => setActiveTab("inpainting")}
            >
              <div className="btn-icon-wrapper inpainting">
                <Eraser size={14} />
              </div>
              <span>{t("settings.inpainting")}</span>
            </button>}
          </div>
          <button
            type="button"
            className={`advanced-mode-toggle ${showAdvanced ? "active" : ""}`}
            onClick={toggleAdvanced}
            aria-pressed={showAdvanced}
          >
            <Sliders size={14} />
            <span>{showAdvanced ? t("settings.basicMode") : t("settings.advancedMode")}</span>
          </button>
        </div>

        {/* Right Settings Form Area */}
        <form onSubmit={handleSubmit} className="preferences-main">
          <div className="preferences-header">
            <div className="header-info">
              <h2>
                {activeTab === "general" && t("settings.generalTitle")}
                {activeTab === "translation" && t("settings.translationTitle")}
                {activeTab === "detection" && t("settings.detectionTitle")}
                {activeTab === "inpainting" && t("settings.inpaintingTitle")}
              </h2>
              <p className="header-desc">
                {activeTab === "general" && t("settings.generalDesc")}
                {activeTab === "translation" && t("settings.translationDesc")}
                {activeTab === "detection" && t("settings.detectionDesc")}
                {activeTab === "inpainting" && t("settings.inpaintingDesc")}
              </p>
            </div>
            <button type="button" className="close-btn-top" onClick={onClose} data-tooltip={t("settings.close")} aria-label={t("settings.close")}>
              <X size={14} />
            </button>
          </div>

          <div className="preferences-body">
            <div className="tab-pane-content">
              {/* GENERAL TAB */}
              {activeTab === "general" && (
                <div className="settings-section">
                  <div className="section-title-label">{t("settings.appearance")}</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.uiLanguage")}</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.ui_language}
                          onChange={(v) => handleAutoSave("ui_language", v)}
                          options={[
                            { value: "en", label: "English" },
                            { value: "ko", label: "한국어" },
                          ]}
                        />
                      </div>
                    </div>
                    <div
                      className="form-row-group"
                      role="radiogroup"
                      aria-label={t("settings.theme")}
                    >
                      <label className="pref-label">{t("settings.theme")}</label>
                      <div className="pref-control-right">
                        <div className="theme-segmented">
                          {themes.map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              role="radio"
                              aria-checked={theme === item.id}
                              aria-label={item.label}
                              className={`theme-segment ${theme === item.id ? "selected" : ""}`}
                              onClick={() => setTheme(item.id)}
                            >
                              <span className="theme-dot" style={{ background: item.preview.accent }} />
                              <span>{item.label}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>


                  {showAdvanced && <>
                    <div className="advanced-settings-note">{t("settings.advancedHint")}</div>
                    <div className="section-title-label">{t("settings.connectionDefaults")}</div>
                    <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.requestTimeout")}</label>
                      <div className="pref-control-right">
                        <NumberStepper
                          label={t("settings.requestTimeout")}
                          value={localSettings.translation_timeout_seconds}
                          min={10}
                          max={300}
                          step={5}
                          onChange={(v) => handleAutoSave("translation_timeout_seconds", v)}
                        />
                      </div>
                    </div>
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.retryCount")}</label>
                      <div className="pref-control-right">
                        <NumberStepper
                          label={t("settings.retryCount")}
                          value={localSettings.translation_max_retries}
                          min={0}
                          max={8}
                          step={1}
                          onChange={(v) => handleAutoSave("translation_max_retries", v)}
                        />
                      </div>
                    </div>
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.retryBackoff")}</label>
                      <div className="pref-control-right">
                        <NumberStepper
                          label={t("settings.retryBackoff")}
                          value={localSettings.translation_retry_backoff_seconds}
                          min={0}
                          max={30}
                          step={1}
                          onChange={(v) => handleAutoSave("translation_retry_backoff_seconds", v)}
                        />
                      </div>
                    </div>
                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.translation_cache_enabled}
                          onChange={(e) => handleAutoSave("translation_cache_enabled", e.target.checked)}
                        />
                        <span>{t("settings.translationCache")}</span>
                      </label>
                    </div>
                    {localSettings.translation_cache_enabled && (
                      <div className="form-row-group">
                        <label className="pref-label">{t("settings.cacheMode")}</label>
                        <div className="pref-control-right">
                          <AppleSelect
                            value={localSettings.translation_cache_mode}
                            onChange={(v) => handleAutoSave("translation_cache_mode", v)}
                            options={[
                              { value: "text_with_context", label: t("settings.cacheModeContext") },
                              { value: "text_only", label: t("settings.cacheModeTextOnly") },
                            ]}
                          />
                        </div>
                      </div>
                    )}
                    </div>
                  </>}
                </div>
              )}

              {/* TRANSLATION TAB */}
              {activeTab === "translation" && (
                <div className="settings-section">
                  <div className="section-title-label">{t("settings.languages")}</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.sourceLanguage")}</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.source_language}
                          onChange={(v) => handleAutoSave("source_language", v)}
                          options={[...SUPPORTED_TRANSLATION_LANGUAGES]}
                        />
                      </div>
                    </div>
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.targetLanguage")}</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.target_language}
                          onChange={(v) => handleAutoSave("target_language", v)}
                          options={[...getTargetLanguageOptions(localSettings.source_language)]}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="section-title-label">{t("settings.activeProvider")}</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.translationProvider")}</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.translation_provider}
                          onChange={(v) => handleAutoSave("translation_provider", v)}
                          options={translationProviderManifests.length > 0
                            ? translationProviderManifests.map((provider) => ({
                                value: provider.selection_value,
                                label: provider.display_name,
                              }))
                            : [
                                { value: "google", label: t("settings.providerGoogle") },
                                { value: "deepl", label: "DeepL Translation API" },
                                { value: "openai", label: "OpenAI (ChatGPT API)" },
                                { value: "claude", label: "Anthropic Claude API" },
                                { value: "papago", label: "Naver Papago API" },
                                { value: "baidu", label: "Baidu Fanyi API" },
                                { value: "ollama", label: t("settings.providerOllama") },
                                { value: "openai_compatible", label: t("settings.providerCompatible") },
                              ]}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Provider Specific Configuration Card */}
                  <div className="section-title-label">{t("settings.providerConfig")}</div>
                  <div className="settings-card">
                    {selectedTranslationManifest && renderCatalogProviderConfig(selectedTranslationManifest)}
                    {/* GOOGLE WEB */}
                    {!selectedTranslationManifest && localSettings.translation_provider === "google" && (
                      <div className="provider-info-block">
                        <HelpCircle className="info-icon" size={16} />
                        <p>{t("settings.googleProviderInfo")}</p>
                      </div>
                    )}

                    {/* DEEPL */}
                    {!selectedTranslationManifest && localSettings.translation_provider === "deepl" && (
                      <div className="form-row-group stack">
                        <label className="pref-label">{t("settings.deeplApiKey")}</label>
                        <input
                          type="password"
                          className="apple-input-text full text-left"
                          placeholder={t("settings.deeplApiKeyPlaceholder")}
                          value={localSettings.translation_api_key}
                          onChange={(e) => handleChange("translation_api_key", e.target.value)}
                          onBlur={() => onSave(localSettings)}
                          onKeyDown={handleKeyDown}
                        />
                        <span className="pref-help-text">{t("settings.deeplApiKeyHelp")}</span>
                      </div>
                    )}

                    {/* OPENAI */}
                    {!selectedTranslationManifest && localSettings.translation_provider === "openai" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">{t("settings.openaiApiKey")}</label>
                          <input
                            type="password"
                            className="apple-input-text full text-left"
                            placeholder="sk-proj-..."
                            value={localSettings.translation_api_key}
                            onChange={(e) => handleChange("translation_api_key", e.target.value)}
                            onBlur={() => { onSave(localSettings); fetchProviderModels(); }}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                        {renderModelSelector()}
                      </>
                    )}

                    {/* CLAUDE */}
                    {!selectedTranslationManifest && localSettings.translation_provider === "claude" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">{t("settings.claudeApiKey")}</label>
                          <input
                            type="password"
                            className="apple-input-text full text-left"
                            placeholder="sk-ant-..."
                            value={localSettings.translation_api_key}
                            onChange={(e) => handleChange("translation_api_key", e.target.value)}
                            onBlur={() => { onSave(localSettings); fetchProviderModels(); }}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                        {renderModelSelector()}
                      </>
                    )}

                    {/* PAPAGO */}
                    {!selectedTranslationManifest && localSettings.translation_provider === "papago" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">{t("settings.papagoClientId")}</label>
                          <input
                            type="text"
                            className="apple-input-text full text-left"
                            placeholder={t("settings.papagoClientIdPlaceholder")}
                            value={localSettings.translation_api_base_url}
                            onChange={(e) => handleChange("translation_api_base_url", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                        <div className="form-row-group stack">
                          <label className="pref-label">{t("settings.papagoClientSecret")}</label>
                          <input
                            type="password"
                            className="apple-input-text full text-left"
                            placeholder={t("settings.papagoClientSecretPlaceholder")}
                            value={localSettings.translation_api_key}
                            onChange={(e) => handleChange("translation_api_key", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                      </>
                    )}

                    {/* BAIDU */}
                    {!selectedTranslationManifest && localSettings.translation_provider === "baidu" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">{t("settings.baiduAppId")}</label>
                          <input
                            type="text"
                            className="apple-input-text full text-left"
                            placeholder={t("settings.baiduAppIdPlaceholder")}
                            value={localSettings.translation_api_base_url}
                            onChange={(e) => handleChange("translation_api_base_url", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                        <div className="form-row-group stack">
                          <label className="pref-label">{t("settings.baiduSecretKey")}</label>
                          <input
                            type="password"
                            className="apple-input-text full text-left"
                            placeholder={t("settings.baiduSecretKeyPlaceholder")}
                            value={localSettings.translation_api_key}
                            onChange={(e) => handleChange("translation_api_key", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                      </>
                    )}

                    {/* OLLAMA */}
                    {!selectedTranslationManifest && localSettings.translation_provider === "ollama" && (
                      <>
                        <div className="provider-info-block">
                          <HelpCircle className="info-icon" size={16} />
                          <p>{t("settings.ollamaProviderInfo")}</p>
                        </div>
                        {renderModelSelector()}
                      </>
                    )}

                    {/* OPENAI COMPATIBLE */}
                    {!selectedTranslationManifest && localSettings.translation_provider === "openai_compatible" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">{t("settings.apiBaseUrl")}</label>
                          <input
                            type="text"
                            className="apple-input-text full text-left"
                            placeholder="http://localhost:1234/v1"
                            value={localSettings.translation_api_base_url}
                            onChange={(e) => handleChange("translation_api_base_url", e.target.value)}
                            onBlur={() => { onSave(localSettings); fetchProviderModels(); }}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                        {renderModelSelector(true)}
                        <div className="form-row-group stack">
                          <label className="pref-label">{t("settings.apiKeyOptional")}</label>
                          <input
                            type="password"
                            className="apple-input-text full text-left"
                            placeholder={t("settings.optionalApiKeyPlaceholder")}
                            value={localSettings.translation_api_key}
                            onChange={(e) => handleChange("translation_api_key", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                      </>
                    )}

                    {/* VISION (Applicable to LLMs) */}
                    {providerCapabilities.visionContext && (
                      <div className="form-row-group stack" style={{ marginTop: "12px", borderTop: "1px solid var(--border-color)", paddingTop: "12px" }}>
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={localSettings.translation_supports_vision}
                            onChange={(e) => handleAutoSave("translation_supports_vision", e.target.checked)}
                          />
                          <span>{t("settings.visionContext")}</span>
                        </label>
                      </div>
                    )}

                    {/* SYSTEM PROMPT (Applicable to LLMs) */}
                    {providerCapabilities.systemPrompt && (
                      <div className="form-row-group stack" style={{ marginTop: "12px", borderTop: "1px solid var(--border-color)", paddingTop: "12px" }}>
                        <label className="pref-label">{t("settings.systemPromptOverride")}</label>
                        <textarea
                          className="apple-textarea-pref"
                          value={localSettings.system_prompt}
                          onChange={(e) => handleChange("system_prompt", e.target.value)}
                          onBlur={() => onSave(localSettings)}
                          placeholder={t("settings.systemPromptPlaceholder")}
                        />
                      </div>
                    )}
                  </div>

                  {showAdvanced && providerCapabilities.llmOptions && (
                    <>
                      <div className="section-title-label">{t("settings.llmOptions")}</div>
                      <div className="settings-card">
                        {renderRangeControl(
                          "translation_llm_temperature",
                          t("settings.temperature"),
                          localSettings.translation_llm_temperature,
                          0,
                          1,
                          0.05
                        )}
                        {renderRangeControl(
                          "translation_llm_top_p",
                          t("settings.topP"),
                          localSettings.translation_llm_top_p,
                          0.1,
                          1,
                          0.05
                        )}
                        <div className="form-row-group">
                          <label className="pref-label">{t("settings.maxTokens")}</label>
                          <div className="pref-control-right">
                            <NumberStepper
                              label={t("settings.maxTokens")}
                              value={localSettings.translation_llm_max_tokens}
                              min={512}
                              max={16384}
                              step={256}
                              onChange={(v) => handleAutoSave("translation_llm_max_tokens", v)}
                            />
                          </div>
                        </div>
                        <p className="model-hint">{t("settings.llmOptionsHelp")}</p>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* DETECTION TAB */}
              {activeTab === "detection" && (
                <div className="settings-section">
                  {detectionManifest && ocrManifest ? (
                    <>
                      <div className="section-title-label">{t("settings.recognitionRules")}</div>
                      <div className="settings-card">
                        {renderCatalogProviderConfig(detectionManifest)}
                      </div>
                      <div className="section-title-label">{t("settings.ocrOptions")}</div>
                      <div className="settings-card">
                        {renderCatalogProviderConfig(ocrManifest)}
                      </div>
                    </>
                  ) : (
                  <>
                  <div className="section-title-label">{t("settings.recognitionRules")}</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.detectionModel")}</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.detect_model}
                          onChange={(v) => handleAutoSave("detect_model", v)}
                          options={[
                            { value: "High Precision (FP32)", label: t("settings.modelHighPrecision") },
                            { value: "Small (INT8)", label: t("settings.modelSmall") },
                          ]}
                        />
                      </div>
                    </div>

                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.tiling_enabled}
                          onChange={(e) => handleAutoSave("tiling_enabled", e.target.checked)}
                        />
                        <span>{t("settings.tilingEnabled")}</span>
                      </label>
                    </div>

                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.bubbles_only}
                          onChange={(e) => handleAutoSave("bubbles_only", e.target.checked)}
                        />
                        <span>{t("settings.bubblesOnly")}</span>
                      </label>
                    </div>
                  </div>

                  <div className="section-title-label">{t("settings.ocrOptions")}</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.ocrEngine")}</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.ocr_engine}
                          onChange={(v) => handleAutoSave("ocr_engine", v)}
                          options={[
                            { value: "balanced", label: t("settings.ocrEngineBalanced") },
                            { value: "fast", label: t("settings.ocrEngineFast") },
                          ]}
                        />
                      </div>
                    </div>
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.ocrPadding")}</label>
                      <div className="pref-control-right">
                        <NumberStepper
                          label={t("settings.ocrPadding")}
                          value={localSettings.ocr_padding}
                          min={0}
                          max={32}
                          step={1}
                          onChange={(v) => handleAutoSave("ocr_padding", v)}
                        />
                      </div>
                    </div>
                    {renderRangeControl(
                      "ocr_crop_scale",
                      t("settings.ocrCropScale"),
                      localSettings.ocr_crop_scale,
                      0.5,
                      3,
                      0.25,
                      (value) => `${value.toFixed(2)}x`
                    )}
                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.adaptive_binarization}
                          onChange={(e) => handleAutoSave("adaptive_binarization", e.target.checked)}
                        />
                        <span>{t("settings.adaptiveBinarization")}</span>
                      </label>
                    </div>
                    {localSettings.adaptive_binarization && renderRangeControl(
                      "adaptive_binarization_strength",
                      t("settings.adaptiveBinarizationStrength"),
                      localSettings.adaptive_binarization_strength,
                      0.5,
                      5,
                      0.25,
                      (value) => value.toFixed(2)
                    )}
                  </div>

                  <div className="section-title-label">{t("settings.directionOptions")}</div>
                  <div className="settings-card">
                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.smart_direction}
                          onChange={(e) => handleAutoSave("smart_direction", e.target.checked)}
                        />
                        <span>{t("settings.smartDirection")}</span>
                      </label>
                    </div>
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.directionOverride")}</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.text_direction_override}
                          onChange={(v) => handleAutoSave("text_direction_override", v)}
                          options={[
                            { value: "auto", label: t("settings.directionAuto") },
                            { value: "horizontal", label: t("settings.directionHorizontal") },
                            { value: "vertical", label: t("settings.directionVertical") },
                          ]}
                        />
                      </div>
                    </div>
                    {renderRangeControl(
                      "line_merge_sensitivity",
                      t("settings.lineMergeSensitivity"),
                      localSettings.line_merge_sensitivity,
                      0.5,
                      2.5,
                      0.1,
                      (value) => value.toFixed(1)
                    )}
                  </div>

                  <div className="section-title-label">{t("settings.confidenceTolerances")}</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.confidenceThreshold")}</label>
                      <div className="pref-control-right flex-align">
                        <input
                          type="range"
                          min="0.1"
                          max="0.9"
                          step="0.05"
                          className="apple-slider"
                          value={localSettings.confidence_threshold}
                          onChange={(e) => handleAutoSave("confidence_threshold", parseFloat(e.target.value))}
                        />
                        <span className="pref-value-indicator">{(localSettings.confidence_threshold * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                  </>
                  )}
                </div>
              )}

              {/* INPAINTING TAB */}
              {activeTab === "inpainting" && (
                <div className="settings-section">
                  {inpaintingManifest ? (
                    <>
                      <div className="section-title-label">{t("settings.inpaintingOptions")}</div>
                      <div className="settings-card">
                        {renderCatalogProviderConfig(inpaintingManifest)}
                      </div>
                    </>
                  ) : (
                  <>
                  <div className="section-title-label">{t("settings.inpaintingOptions")}</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.inpaintingEngine")}</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.inpaint_engine}
                          onChange={(v) => handleAutoSave("inpaint_engine", v)}
                          options={[
                            { value: "lama", label: t("settings.inpaintingEngineBalanced") },
                            { value: "opencv", label: t("settings.inpaintingEngineFast") },
                          ]}
                        />
                      </div>
                    </div>

                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.inpaint_use_textbox_only}
                          onChange={(e) => handleAutoSave("inpaint_use_textbox_only", e.target.checked)}
                        />
                        <span>{t("settings.cleanTextboxOnly")}</span>
                      </label>
                    </div>

                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.inpaint_clip_to_bubble}
                          onChange={(e) => handleAutoSave("inpaint_clip_to_bubble", e.target.checked)}
                        />
                        <span>{t("settings.clipInpaintingMask")}</span>
                      </label>
                    </div>
                  </div>

                  <div className="section-title-label">{t("settings.maskTolerances")}</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">{t("settings.maskDilation")}</label>
                      <div className="pref-control-right flex-align">
                        <input
                          type="range"
                          min="0"
                          max="10"
                          className="apple-slider"
                          value={localSettings.inpaint_mask_dilation}
                          onChange={(e) => handleAutoSave("inpaint_mask_dilation", parseInt(e.target.value))}
                        />
                        <span className="pref-value-indicator">{localSettings.inpaint_mask_dilation}px</span>
                      </div>
                    </div>
                  </div>
                  </>
                  )}
                </div>
              )}

            </div>
          </div>
        </form>
      </div>

      <style>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: var(--scrim);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 100;
        }

        .modal-content {
          background: var(--bg-panel);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-lg);
          width: 760px;
          height: 520px;
          display: flex;
          flex-direction: row;
          box-shadow: var(--shadow-lg);
          overflow: hidden;
          animation: scaleUp 0.18s var(--ease-standard);
        }

        .modal-content:focus,
        .modal-content:focus-visible {
          outline: none;
        }

        @keyframes scaleUp {
          from { transform: scale(0.96); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }

        /* Sidebar styling matching Antigravity */
        .preferences-sidebar {
          width: 210px;
          background-color: var(--bg-sidebar);
          border-right: 1px solid var(--border-color);
          display: flex;
          flex-direction: column;
          padding: 16px 8px;
        }

        .sidebar-header-pref {
          padding: 6px 12px 14px;
        }

        .sidebar-header-pref h3 {
          font-size: 11px;
          font-weight: 700;
          color: var(--text-tertiary);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .sidebar-menu-pref {
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .advanced-mode-toggle {
          display: flex;
          align-items: center;
          gap: 8px;
          width: calc(100% - 16px);
          min-height: 34px;
          margin: auto 8px 0;
          padding: 0 10px;
          border: 1px solid var(--border-color);
          border-radius: var(--radius-md);
          background: var(--fill-3);
          color: var(--text-secondary);
          font: 600 11.5px/1 var(--font-family);
          cursor: pointer;
        }

        .advanced-mode-toggle:hover,
        .advanced-mode-toggle.active {
          background: var(--fill-hover);
          color: var(--text-primary);
        }

        .menu-btn-pref {
          background: transparent;
          border: none;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 12px;
          border-radius: 6px;
          color: var(--text-secondary);
          font-size: 12.5px;
          font-weight: 500;
          text-align: left;
          cursor: pointer;
          transition: all 0.15s;
        }

        .menu-btn-pref:hover {
          background: var(--fill-3);
          color: var(--text-primary);
        }

        .menu-btn-pref.active {
          background: var(--bg-input-focus);
          color: var(--text-primary);
          font-weight: 600;
        }

        .btn-icon-wrapper {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 22px;
          height: 22px;
          border-radius: 5px;
          color: white;
        }

        .btn-icon-wrapper.general { background-color: #8e8e93; }
        .btn-icon-wrapper.translation { background-color: var(--system-blue); }
        .btn-icon-wrapper.detection { background-color: var(--system-green); }
        .btn-icon-wrapper.inpainting { background-color: var(--system-orange); }

        /* Main settings content pane */
        .preferences-main {
          flex: 1;
          display: flex;
          flex-direction: column;
          height: 100%;
          background-color: var(--bg-panel);
        }

        .preferences-header {
          padding: 20px 24px 14px;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          border-bottom: 1px solid var(--border-color);
        }

        .header-info {
          flex: 1;
        }

        .header-info h2 {
          font-size: 15px;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 4px;
        }

        .header-desc {
          font-size: 11px;
          color: var(--text-secondary);
          line-height: 1.4;
        }

        .close-btn-top {
          background: transparent;
          border: none;
          color: var(--text-tertiary);
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
        }

        .close-btn-top:hover {
          background: var(--bg-input);
          color: var(--text-primary);
        }

        .preferences-body {
          flex: 1;
          overflow-y: auto;
          padding: 20px 24px;
        }

        .tab-pane-content {
          height: 100%;
        }

        .settings-section {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .advanced-settings-note {
          padding: 9px 11px;
          border: 1px solid var(--accent-border-subtle);
          border-radius: var(--radius-md);
          background: var(--accent-bg-subtle);
          color: var(--text-secondary);
          font-size: 11px;
          line-height: 1.45;
        }

        .section-title-label {
          font-size: 10.5px;
          font-weight: 700;
          color: var(--text-tertiary);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 2px;
        }

        /* Apple-style card panel */
        .settings-card {
          background: var(--bg-input);
          border: 1px solid var(--border-color);
          border-radius: 10px;
          padding: 8px 16px;
          display: flex;
          flex-direction: column;
        }

        .form-row-group {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px solid var(--border-color);
          min-height: 38px;
        }

        .form-row-group:last-child {
          border-bottom: none;
        }

        .form-row-group.border-top {
          border-top: 1px solid var(--border-color);
          margin-top: 8px;
          padding-top: 12px;
        }

        .form-row-group.stack {
          flex-direction: column;
          align-items: flex-start;
          gap: 6px;
          border-bottom: none;
          padding: 8px 0;
        }

        .form-row-group.checkbox-row {
          justify-content: flex-start;
          border-bottom: none;
        }

        .pref-label {
          font-size: 12.5px;
          font-weight: 500;
          color: var(--text-primary);
          flex: 1.2;
          text-align: left;
        }

        .pref-control-right {
          flex: 2;
          display: flex;
          justify-content: flex-end;
          align-items: center;
        }

        .pref-control-right.flex-align {
          gap: 8px;
        }

        .pref-value-indicator {
          font-size: 11px;
          font-weight: 600;
          min-width: 32px;
          text-align: right;
          color: var(--text-secondary);
        }

        .apple-input-text {
          background: var(--field-bg);
          border: 1px solid var(--border-color);
          border-radius: 6px;
          color: var(--text-primary);
          padding: 5px 8px;
          font-size: 12px;
          width: 80px;
          text-align: center;
          outline: none;
          transition: border-color 0.15s;
        }

        .apple-input-text.full {
          width: 100%;
        }

        .apple-input-text:focus {
          border-color: var(--system-blue);
        }

        .apple-textarea-pref {
          background: var(--field-bg);
          border: 1px solid var(--border-color);
          border-radius: 6px;
          color: var(--text-primary);
          padding: 8px 10px;
          font-size: 12px;
          width: 100%;
          height: 70px;
          resize: none;
          outline: none;
          transition: border-color 0.15s;
        }

        .apple-textarea-pref:focus {
          border-color: var(--system-blue);
        }

        .theme-swatch-grid {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-6);
        }
        .theme-swatch {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-3);
          background: none;
          border: none;
          padding: 0;
          cursor: pointer;
        }
        .theme-preview {
          position: relative;
          display: block;
          width: 76px;
          height: 52px;
          border-radius: var(--radius-md);
          border: 1px solid var(--separator);
          overflow: hidden;
          box-shadow: var(--shadow-sm);
          transition: box-shadow 0.15s ease, transform 0.15s ease;
        }
        .theme-swatch:hover .theme-preview {
          transform: translateY(-1px);
          box-shadow: var(--shadow-md);
        }
        .theme-swatch.selected .theme-preview {
          outline: 2px solid var(--system-blue);
          outline-offset: 2px;
        }
        .theme-preview-bar {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 12px;
        }
        .theme-preview-panel {
          position: absolute;
          left: 8px;
          top: 20px;
          width: 34px;
          height: 22px;
          border-radius: 4px;
        }
        .theme-preview-accent {
          position: absolute;
          right: 8px;
          bottom: 8px;
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }
        .theme-swatch-label {
          font-size: 12px;
          color: var(--text-secondary);
        }
        .theme-swatch.selected .theme-swatch-label {
          color: var(--text-primary);
          font-weight: 600;
        }

        .theme-segmented {
          display: inline-flex;
          width: 100%;
          max-width: 250px;
          padding: 2px;
          gap: 2px;
          border-radius: var(--radius-md);
          border: 1px solid var(--border-color);
          background: var(--field-bg);
        }

        .theme-segment {
          flex: 1;
          min-width: 0;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          height: 26px;
          padding: 0 8px;
          border: none;
          border-radius: calc(var(--radius-md) - 2px);
          background: transparent;
          color: var(--text-secondary);
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
        }

        .theme-segment:hover {
          color: var(--text-primary);
          background: var(--fill-3);
        }

        .theme-segment.selected {
          color: var(--text-primary);
          background: var(--bg-panel);
          box-shadow: var(--shadow-sm);
        }

        .theme-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          flex: 0 0 auto;
        }

        .model-hint {
          font-size: 11.5px;
          color: var(--text-tertiary);
          padding: 4px 2px;
        }
        .model-error {
          font-size: 11.5px;
          color: var(--system-red);
          padding: 4px 2px;
        }

        .apple-select-pref {
          width: 100%;
          max-width: 250px;
          appearance: none;
          -webkit-appearance: none;
          background-color: var(--field-bg);
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 10px center;
          border: 1px solid var(--border-color);
          border-radius: var(--radius-md);
          color: var(--text-primary);
          padding: var(--space-3) var(--space-10) var(--space-3) var(--space-4);
          font-size: 12.5px;
          font-family: var(--font-family);
          outline: none;
          cursor: pointer;
          transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
        }

        .apple-select-pref:hover {
          background-color: var(--bg-input-focus);
        }

        .apple-select-pref:focus {
          border-color: var(--border-focus);
          box-shadow: var(--focus-ring-shadow);
        }

        /* Ensure the native option popup is readable in both themes
           (belt-and-suspenders alongside color-scheme). */
        .apple-select-pref option {
          background-color: var(--bg-panel);
          color: var(--text-primary);
        }

        .checkbox-label {
          display: flex;
          align-items: center;
          gap: 10px;
          cursor: pointer;
          font-size: 12.5px;
          color: var(--text-secondary);
        }

        .checkbox-label input[type="checkbox"] {
          accent-color: var(--system-blue);
          width: 14px;
          height: 14px;
          cursor: pointer;
        }

        .apple-slider {
          flex: 1;
          accent-color: var(--system-blue);
          height: 4px;
          border-radius: 2px;
          background: var(--separator-strong);
          cursor: pointer;
        }

        .flex-space-between {
          display: flex;
          justify-content: space-between;
          width: 100%;
          align-items: center;
        }

        .refresh-btn {
          background: transparent;
          border: none;
          color: var(--system-blue);
          font-size: 10px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .refresh-btn:disabled {
          opacity: 0.5;
        }

        .provider-info-block {
          display: flex;
          align-items: center;
          gap: 10px;
          background: var(--accent-bg-subtle);
          border: 1px solid var(--accent-border-subtle);
          border-radius: 6px;
          padding: 8px 12px;
          margin: 4px 0;
        }

        .provider-info-block p {
          font-size: 11.5px;
          color: var(--text-secondary);
          margin: 0;
          line-height: 1.4;
        }

        .info-icon {
          color: var(--system-blue);
          flex-shrink: 0;
        }

        .pref-help-text {
          font-size: 10px;
          color: var(--text-tertiary);
          margin-top: 2px;
        }

        .pref-value-pill {
          min-width: 44px;
          padding: 2px 7px;
          border-radius: 6px;
          background: var(--bg-panel);
          color: var(--text-secondary);
          border: 1px solid var(--border-color);
          font-size: 11px;
          font-variant-numeric: tabular-nums;
          text-align: center;
        }

        .pref-range {
          width: 100%;
          accent-color: var(--accent-primary);
        }

        .spin {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
