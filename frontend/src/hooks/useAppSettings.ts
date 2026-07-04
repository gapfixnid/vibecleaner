import { useCallback, useState, type Dispatch, type SetStateAction } from "react";
import * as api from "../services/api";
import { getStoredUiLanguage, rememberUiLanguage } from "../i18n";
import { DEFAULT_TRANSLATION_OPTIONS } from "../translationSettings";
import type { Settings } from "../types";

const DEFAULT_SETTINGS: Settings = {
  translation_model: "",
  translation_provider: "google",
  translation_api_base_url: "",
  translation_api_key: "",
  translation_api_key_configured: false,
  translation_timeout_seconds: DEFAULT_TRANSLATION_OPTIONS.timeoutSeconds,
  translation_supports_vision: false,
  translation_cache_enabled: DEFAULT_TRANSLATION_OPTIONS.cacheEnabled,
  translation_cache_mode: DEFAULT_TRANSLATION_OPTIONS.cacheMode,
  translation_max_retries: DEFAULT_TRANSLATION_OPTIONS.maxRetries,
  translation_retry_backoff_seconds: DEFAULT_TRANSLATION_OPTIONS.retryBackoffSeconds,
  translation_llm_temperature: DEFAULT_TRANSLATION_OPTIONS.temperature,
  translation_llm_top_p: DEFAULT_TRANSLATION_OPTIONS.topP,
  translation_llm_max_tokens: DEFAULT_TRANSLATION_OPTIONS.maxTokens,
  ui_language: getStoredUiLanguage(),
  source_language: "Japanese",
  target_language: "Korean",
  system_prompt: "",
  detect_model: "",
  confidence_threshold: 0.45,
  tiling_enabled: true,
  bubbles_only: false,
  min_font_size: 6,
  max_font_size: 48,
  default_font_size: 18,
  inpaint_mask_dilation: 2,
  inpaint_use_textbox_only: true,
  inpaint_clip_to_bubble: true,
};

export function useAppSettings() {
  const [settings, setSettingsState] = useState<Settings>(DEFAULT_SETTINGS);

  const setSettings = useCallback<Dispatch<SetStateAction<Settings>>>((next) => {
    setSettingsState((prev) => {
      const resolved = typeof next === "function" ? next(prev) : next;
      rememberUiLanguage(resolved.ui_language);
      return resolved;
    });
  }, []);

  const handleSaveSettings = useCallback(async (updated: Settings) => {
    try {
      const saved = await api.updateSettings(updated);
      setSettings(saved);
    } catch (e) {
      console.error("Failed to auto-save settings", e);
    }
  }, [setSettings]);

  return {
    settings,
    setSettings,
    handleSaveSettings,
  };
}
