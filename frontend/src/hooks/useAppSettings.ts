import { useCallback, useState } from "react";
import * as api from "../services/api";
import type { Settings } from "../types";

const DEFAULT_SETTINGS: Settings = {
  translation_model: "",
  translation_provider: "google",
  translation_api_base_url: "",
  translation_api_key: "",
  translation_api_key_configured: false,
  translation_timeout_seconds: 90,
  translation_supports_vision: false,
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
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  const handleSaveSettings = useCallback(async (updated: Settings) => {
    try {
      const saved = await api.updateSettings(updated);
      setSettings(saved);
    } catch (e) {
      console.error("Failed to auto-save settings", e);
    }
  }, []);

  return {
    settings,
    setSettings,
    handleSaveSettings,
  };
}
