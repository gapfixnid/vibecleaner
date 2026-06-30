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
  HelpCircle
} from "lucide-react";
import * as api from "../services/api";
import type { Settings } from "../types";
import type { ThemeMeta } from "../themes";
import { NumberStepper } from "./NumberStepper";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: Settings;
  onSave: (updated: Settings) => void;
  backendUrl: string;
  theme: string;
  setTheme: (id: string) => void;
  themes: ThemeMeta[];
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
}) => {
  const [localSettings, setLocalSettings] = useState<Settings>({ ...settings });
  const [providerModels, setProviderModels] = useState<string[]>([]);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>("general");

  useEffect(() => {
    setLocalSettings({ ...settings });
  }, [settings, isOpen]);

  const LLM_PROVIDERS = ["openai", "claude", "ollama", "openai_compatible"];
  const providerNeedsKey = (p: string) => p === "openai" || p === "claude";

  // Fetch the live model list for the current LLM provider using the entered
  // credentials. Doubles as API-key validation.
  const fetchProviderModels = async () => {
    const provider = localSettings.translation_provider;
    if (!LLM_PROVIDERS.includes(provider)) {
      setProviderModels([]);
      setModelsError(null);
      return;
    }
    if (providerNeedsKey(provider) && !localSettings.translation_api_key) {
      setProviderModels([]);
      setModelsError(null);
      return;
    }
    setIsLoadingModels(true);
    setModelsError(null);
    try {
      const res = await api.getTranslationModels(
        provider,
        localSettings.translation_api_key,
        localSettings.translation_api_base_url
      );
      setProviderModels(res.models || []);
      setModelsError(res.error || null);
    } catch (e) {
      console.warn("Failed to fetch provider models", e);
      setProviderModels([]);
      setModelsError("모델 목록을 불러오지 못했습니다.");
    } finally {
      setIsLoadingModels(false);
    }
  };

  useEffect(() => {
    if (isOpen && LLM_PROVIDERS.includes(localSettings.translation_provider)) {
      fetchProviderModels();
    } else {
      setProviderModels([]);
      setModelsError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, localSettings.translation_provider]);

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

  const handleChange = (key: keyof Settings, value: any) => {
    setLocalSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleAutoSave = (key: keyof Settings, value: any) => {
    const updated = {
      ...localSettings,
      [key]: value,
    };
    setLocalSettings(updated);
    onSave(updated);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.currentTarget.blur();
    }
  };

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
          <label className="pref-label">Model</label>
          <button type="button" className="refresh-btn" onClick={fetchProviderModels} disabled={isLoadingModels}>
            <RefreshCw size={11} className={isLoadingModels ? "spin" : ""} />
            <span>Refresh</span>
          </button>
        </div>
        {needsKey && !localSettings.translation_api_key ? (
          <p className="model-hint">Enter your API key to load models.</p>
        ) : isLoadingModels ? (
          <p className="model-hint">Loading models…</p>
        ) : modelsError ? (
          <p className="model-error">{modelsError}</p>
        ) : providerModels.length > 0 ? (
          <AppleSelect
            value={localSettings.translation_model}
            onChange={(v) => handleAutoSave("translation_model", v)}
            options={[
              { value: "", label: "Select a model..." },
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
          <p className="model-hint">No models found.</p>
        )}
      </div>
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        tabIndex={-1}
        ref={contentRef}
      >
        
        {/* Left Category Sidebar */}
        <div className="preferences-sidebar">
          <div className="sidebar-header-pref">
            <h3>Preferences</h3>
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
              <span>General</span>
            </button>
            <button 
              type="button" 
              className={`menu-btn-pref ${activeTab === "translation" ? "active" : ""}`}
              onClick={() => setActiveTab("translation")}
            >
              <div className="btn-icon-wrapper translation">
                <Languages size={14} />
              </div>
              <span>Translation</span>
            </button>
            <button 
              type="button" 
              className={`menu-btn-pref ${activeTab === "detection" ? "active" : ""}`}
              onClick={() => setActiveTab("detection")}
            >
              <div className="btn-icon-wrapper detection">
                <Scan size={14} />
              </div>
              <span>Detection</span>
            </button>
            <button 
              type="button" 
              className={`menu-btn-pref ${activeTab === "inpainting" ? "active" : ""}`}
              onClick={() => setActiveTab("inpainting")}
            >
              <div className="btn-icon-wrapper inpainting">
                <Eraser size={14} />
              </div>
              <span>Inpainting</span>
            </button>
          </div>
        </div>

        {/* Right Settings Form Area */}
        <form onSubmit={handleSubmit} className="preferences-main">
          <div className="preferences-header">
            <div className="header-info">
              <h2>
                {activeTab === "general" && "General Settings"}
                {activeTab === "translation" && "Translation Engine"}
                {activeTab === "detection" && "Detection & OCR"}
                {activeTab === "inpainting" && "Inpainting & Cleaning"}
              </h2>
              <p className="header-desc">
                {activeTab === "general" && "Manage general preferences, font size boundaries, and timeouts."}
                {activeTab === "translation" && "Select from offline, local, or cloud API translation engines."}
                {activeTab === "detection" && "Configure bubble detection models, threshold tolerances, and tiling settings."}
                {activeTab === "inpainting" && "Tweak background LaMa inpainting mask boundaries and dilation."}
              </p>
            </div>
            <button type="button" className="close-btn-top" onClick={onClose} data-tooltip="Close" aria-label="Close settings">
              <X size={14} />
            </button>
          </div>

          <div className="preferences-body">
            <div className="tab-pane-content">
              {/* GENERAL TAB */}
              {activeTab === "general" && (
                <div className="settings-section">
                  <div className="section-title-label">Appearance</div>
                  <div className="settings-card">
                    <div
                      className="theme-swatch-grid"
                      role="radiogroup"
                      aria-label="Theme"
                    >
                      {themes.map((t) => (
                        <button
                          key={t.id}
                          type="button"
                          role="radio"
                          aria-checked={theme === t.id}
                          aria-label={t.label}
                          className={`theme-swatch ${theme === t.id ? "selected" : ""}`}
                          onClick={() => setTheme(t.id)}
                        >
                          <span className="theme-preview" style={{ background: t.preview.body }}>
                            <span className="theme-preview-bar" style={{ background: t.preview.bar }} />
                            <span className="theme-preview-panel" style={{ background: t.preview.panel }} />
                            <span className="theme-preview-accent" style={{ background: t.preview.accent }} />
                          </span>
                          <span className="theme-swatch-label">{t.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>


                  <div className="section-title-label">Connection Defaults</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">Request Timeout (sec)</label>
                      <div className="pref-control-right">
                        <NumberStepper
                          label="Request timeout in seconds"
                          value={localSettings.translation_timeout_seconds}
                          min={10}
                          max={300}
                          step={5}
                          onChange={(v) => handleAutoSave("translation_timeout_seconds", v)}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TRANSLATION TAB */}
              {activeTab === "translation" && (
                <div className="settings-section">
                  <div className="section-title-label">Languages</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">Source Language (OCR)</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.source_language}
                          onChange={(v) => handleAutoSave("source_language", v)}
                          options={[
                            { value: "Japanese", label: "Japanese" },
                            { value: "Korean", label: "Korean" },
                            { value: "Chinese", label: "Chinese" },
                            { value: "English", label: "English" },
                          ]}
                        />
                      </div>
                    </div>
                    <div className="form-row-group">
                      <label className="pref-label">Target Language (Translation)</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.target_language}
                          onChange={(v) => handleAutoSave("target_language", v)}
                          options={[
                            { value: "Korean", label: "Korean" },
                            { value: "English", label: "English" },
                            { value: "Japanese", label: "Japanese" },
                            { value: "Chinese", label: "Chinese" },
                          ]}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="section-title-label">Active Provider</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">Translation Provider</label>
                      <div className="pref-control-right">
                        <AppleSelect
                          value={localSettings.translation_provider}
                          onChange={(v) => handleAutoSave("translation_provider", v)}
                          options={[
                            { value: "google", label: "Google Translate (Free Web · Default)" },
                            { value: "deepl", label: "DeepL Translation API" },
                            { value: "openai", label: "OpenAI (ChatGPT API)" },
                            { value: "claude", label: "Anthropic Claude API" },
                            { value: "papago", label: "Naver Papago API" },
                            { value: "baidu", label: "Baidu Fanyi API" },
                            { value: "ollama", label: "Ollama (Local LLM)" },
                            { value: "openai_compatible", label: "OpenAI Compatible (Local/Custom)" },
                          ]}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Provider Specific Configuration Card */}
                  <div className="section-title-label">Provider Credentials & Config</div>
                  <div className="settings-card">
                    {/* GOOGLE WEB */}
                    {localSettings.translation_provider === "google" && (
                      <div className="provider-info-block">
                        <HelpCircle className="info-icon" size={16} />
                        <p>Google Translate uses a public web-scraping translator API. No credential setup is required. Requires an active internet connection.</p>
                      </div>
                    )}

                    {/* DEEPL */}
                    {localSettings.translation_provider === "deepl" && (
                      <div className="form-row-group stack">
                        <label className="pref-label">DeepL API Authentication Key</label>
                        <input
                          type="password"
                          className="apple-input-text full text-left"
                          placeholder="Paste your DeepL API key here..."
                          value={localSettings.translation_api_key}
                          onChange={(e) => handleChange("translation_api_key", e.target.value)}
                          onBlur={() => onSave(localSettings)}
                          onKeyDown={handleKeyDown}
                        />
                        <span className="pref-help-text">Free API Keys typically end with <code>:fx</code>.</span>
                      </div>
                    )}

                    {/* OPENAI */}
                    {localSettings.translation_provider === "openai" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">OpenAI API Key</label>
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
                    {localSettings.translation_provider === "claude" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">Anthropic Claude API Key</label>
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
                    {localSettings.translation_provider === "papago" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">Papago Client ID</label>
                          <input
                            type="text"
                            className="apple-input-text full text-left"
                            placeholder="Naver Cloud Platform Client ID..."
                            value={localSettings.translation_api_base_url}
                            onChange={(e) => handleChange("translation_api_base_url", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                        <div className="form-row-group stack">
                          <label className="pref-label">Papago Client Secret</label>
                          <input
                            type="password"
                            className="apple-input-text full text-left"
                            placeholder="Naver Cloud Platform Client Secret..."
                            value={localSettings.translation_api_key}
                            onChange={(e) => handleChange("translation_api_key", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                      </>
                    )}

                    {/* BAIDU */}
                    {localSettings.translation_provider === "baidu" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">Baidu APP ID</label>
                          <input
                            type="text"
                            className="apple-input-text full text-left"
                            placeholder="Baidu Translation Portal APP ID..."
                            value={localSettings.translation_api_base_url}
                            onChange={(e) => handleChange("translation_api_base_url", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                        <div className="form-row-group stack">
                          <label className="pref-label">Baidu Secret Key</label>
                          <input
                            type="password"
                            className="apple-input-text full text-left"
                            placeholder="Baidu Translation Portal Secret Key..."
                            value={localSettings.translation_api_key}
                            onChange={(e) => handleChange("translation_api_key", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                      </>
                    )}

                    {/* OLLAMA */}
                    {localSettings.translation_provider === "ollama" && (
                      <>
                        <div className="provider-info-block">
                          <HelpCircle className="info-icon" size={16} />
                          <p>Connects to your local Ollama daemon at http://127.0.0.1:11434. Make sure Ollama is running, then pick a model below.</p>
                        </div>
                        {renderModelSelector()}
                      </>
                    )}

                    {/* OPENAI COMPATIBLE */}
                    {localSettings.translation_provider === "openai_compatible" && (
                      <>
                        <div className="form-row-group stack">
                          <label className="pref-label">API Base URL</label>
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
                          <label className="pref-label">API Key (Optional)</label>
                          <input
                            type="password"
                            className="apple-input-text full text-left"
                            placeholder="Optional custom LLM API key..."
                            value={localSettings.translation_api_key}
                            onChange={(e) => handleChange("translation_api_key", e.target.value)}
                            onBlur={() => onSave(localSettings)}
                            onKeyDown={handleKeyDown}
                          />
                        </div>
                      </>
                    )}

                    {/* VISION (Applicable to LLMs) */}
                    {["ollama", "openai_compatible", "openai", "claude"].includes(localSettings.translation_provider) && (
                      <div className="form-row-group stack" style={{ marginTop: "12px", borderTop: "1px solid var(--border-color)", paddingTop: "12px" }}>
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={localSettings.translation_supports_vision}
                            onChange={(e) => handleAutoSave("translation_supports_vision", e.target.checked)}
                          />
                          <span>Send page image for visual context (turn off for text-only models, e.g. llama.cpp without mmproj)</span>
                        </label>
                      </div>
                    )}

                    {/* SYSTEM PROMPT (Applicable to LLMs) */}
                    {["ollama", "openai_compatible", "openai", "claude"].includes(localSettings.translation_provider) && (
                      <div className="form-row-group stack" style={{ marginTop: "12px", borderTop: "1px solid var(--border-color)", paddingTop: "12px" }}>
                        <label className="pref-label">System Prompt Override</label>
                        <textarea
                          className="apple-textarea-pref"
                          value={localSettings.system_prompt}
                          onChange={(e) => handleChange("system_prompt", e.target.value)}
                          onBlur={() => onSave(localSettings)}
                          placeholder="Enter custom context guidelines for the LLM translation engine..."
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* DETECTION TAB */}
              {activeTab === "detection" && (
                <div className="settings-section">
                  <div className="section-title-label">Recognition Rules</div>
                  <div className="settings-card">
                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.tiling_enabled}
                          onChange={(e) => handleAutoSave("tiling_enabled", e.target.checked)}
                        />
                        <span>Tiling Enabled (Increases detection quality for small bubbles)</span>
                      </label>
                    </div>

                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.bubbles_only}
                          onChange={(e) => handleAutoSave("bubbles_only", e.target.checked)}
                        />
                        <span>Speech Bubbles Only (Ignore free-floating sfx text)</span>
                      </label>
                    </div>
                  </div>

                  <div className="section-title-label">Confidence Tolerances</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">Confidence Threshold</label>
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
                </div>
              )}

              {/* INPAINTING TAB */}
              {activeTab === "inpainting" && (
                <div className="settings-section">
                  <div className="section-title-label">Inpainting Options</div>
                  <div className="settings-card">
                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.inpaint_use_textbox_only}
                          onChange={(e) => handleAutoSave("inpaint_use_textbox_only", e.target.checked)}
                        />
                        <span>Clean Text Box Areas Only (Recommended)</span>
                      </label>
                    </div>

                    <div className="form-row-group checkbox-row">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={localSettings.inpaint_clip_to_bubble}
                          onChange={(e) => handleAutoSave("inpaint_clip_to_bubble", e.target.checked)}
                        />
                        <span>Clip Inpainting Mask to speech bubble stroke edges</span>
                      </label>
                    </div>
                  </div>

                  <div className="section-title-label">Mask tolerances</div>
                  <div className="settings-card">
                    <div className="form-row-group">
                      <label className="pref-label">Mask Dilation (Expansion)</label>
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
          animation: scaleUp 0.18s cubic-bezier(0.25, 0.8, 0.25, 1);
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
        .btn-icon-wrapper.translation { background-color: #007aff; }
        .btn-icon-wrapper.detection { background-color: #34c759; }
        .btn-icon-wrapper.inpainting { background-color: #ff9500; }

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
          box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.2);
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
          background: rgba(10, 132, 255, 0.08);
          border: 1px solid rgba(10, 132, 255, 0.2);
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
