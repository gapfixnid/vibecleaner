# modules/config.py
# Centralized application configuration.
#
# Usage:
#   from modules.config import config          # AppConfig singleton
#   from modules.config import APP_DATA_DIR    # module-level constants
#   config.TRANSLATION_PROVIDER = "google"     # read / write settings
#   config.load()                              # reload from disk
#   config.save()                              # persist to disk

from __future__ import annotations

import json
import logging
import os
import platform
from dataclasses import dataclass, field, asdict
from typing import Any

import cv2
import numpy as np

from app.version import APP_NAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants (never change at runtime)
# ---------------------------------------------------------------------------

OLLAMA_API_URL = "http://127.0.0.1:11434"


def _get_app_data_dir() -> str:
    """Return the OS-specific application data directory."""
    if platform.system() == "Windows":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base_dir, APP_NAME)
    if platform.system() == "Darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    # Linux / Unix
    return os.path.expanduser(f"~/.config/{APP_NAME}")


APP_DATA_DIR: str = _get_app_data_dir()
os.makedirs(APP_DATA_DIR, exist_ok=True)
SETTINGS_FILE_PATH: str = os.path.join(APP_DATA_DIR, "settings.json")

# ---------------------------------------------------------------------------
# AppConfig — mutable settings container (single instance: `config`)
# ---------------------------------------------------------------------------


@dataclass
class AppConfig:
    # -- Translation --------------------------------------------------------
    translation_model: str = ""
    translation_provider: str = "google"
    translation_api_base_url: str = ""
    translation_api_key: str = ""
    translation_timeout_seconds: int = 90
    translation_supports_vision: bool = False
    translation_cache_enabled: bool = True
    translation_cache_mode: str = "text_with_context"
    translation_max_retries: int = 2
    translation_retry_backoff_seconds: int = 2
    translation_llm_temperature: float = 0.1
    translation_llm_top_p: float = 0.95
    translation_llm_max_tokens: int = 4096
    system_prompt: str = ""

    # -- Languages ----------------------------------------------------------
    ui_language: str = "en"
    source_language: str = "Japanese"
    target_language: str = "Korean"

    # -- Detection ----------------------------------------------------------
    detect_model: str = "High Precision (FP32)"
    confidence_threshold: float = 0.45
    tiling_enabled: bool = True
    bubbles_only: bool = False

    # -- OCR ----------------------------------------------------------------
    ocr_engine: str = "balanced"
    ocr_padding: int = 8
    ocr_crop_scale: float = 1.5
    line_merge_sensitivity: float = 1.2
    adaptive_binarization: bool = True
    adaptive_binarization_strength: float = 2.0
    smart_direction: bool = True
    text_direction_override: str = "auto"

    # -- Rendering ----------------------------------------------------------
    min_font_size: float = 6.0
    max_font_size: float = 48.0
    default_font_size: float = 18.0

    # -- Inpainting ---------------------------------------------------------
    inpaint_engine: str = "lama"
    inpaint_mask_dilation: int = 2
    inpaint_use_textbox_only: bool = True
    inpaint_clip_to_bubble: bool = True
    setup_completed: bool = False

    @property
    def DETECT_MODEL(self) -> str:
        return self.detect_model

    @DETECT_MODEL.setter
    def DETECT_MODEL(self, value: str) -> None:
        self.detect_model = value

    @property
    def CONFIDENCE_THRESHOLD(self) -> float:
        return self.confidence_threshold

    @CONFIDENCE_THRESHOLD.setter
    def CONFIDENCE_THRESHOLD(self, value: float) -> None:
        self.confidence_threshold = value

    @property
    def TILING_ENABLED(self) -> bool:
        return self.tiling_enabled

    @TILING_ENABLED.setter
    def TILING_ENABLED(self, value: bool) -> None:
        self.tiling_enabled = value

    @property
    def BUBBLES_ONLY(self) -> bool:
        return self.bubbles_only

    @BUBBLES_ONLY.setter
    def BUBBLES_ONLY(self, value: bool) -> None:
        self.bubbles_only = value

    @property
    def OCR_ENGINE(self) -> str:
        return self.ocr_engine

    @OCR_ENGINE.setter
    def OCR_ENGINE(self, value: str) -> None:
        self.ocr_engine = value

    @property
    def OCR_PADDING(self) -> int:
        return self.ocr_padding

    @OCR_PADDING.setter
    def OCR_PADDING(self, value: int) -> None:
        self.ocr_padding = value

    @property
    def OCR_CROP_SCALE(self) -> float:
        return self.ocr_crop_scale

    @OCR_CROP_SCALE.setter
    def OCR_CROP_SCALE(self, value: float) -> None:
        self.ocr_crop_scale = value

    @property
    def ADAPTIVE_BINARIZATION(self) -> bool:
        return self.adaptive_binarization

    @ADAPTIVE_BINARIZATION.setter
    def ADAPTIVE_BINARIZATION(self, value: bool) -> None:
        self.adaptive_binarization = value

    @property
    def SMART_DIRECTION(self) -> bool:
        return self.smart_direction

    @SMART_DIRECTION.setter
    def SMART_DIRECTION(self, value: bool) -> None:
        self.smart_direction = value

    # -----------------------------------------------------------------------
    # Mapping: JSON key → dataclass field name  (round-trip safe)
    # -----------------------------------------------------------------------
    _FIELD_MAP: dict[str, str] = field(
        init=False,
        repr=False,
        compare=False,
        default_factory=lambda: {
            "translation_model": "translation_model",
            "translation_provider": "translation_provider",
            "translation_api_base_url": "translation_api_base_url",
            "translation_api_key": "translation_api_key",
            "translation_timeout_seconds": "translation_timeout_seconds",
            "translation_supports_vision": "translation_supports_vision",
            "translation_cache_enabled": "translation_cache_enabled",
            "translation_cache_mode": "translation_cache_mode",
            "translation_max_retries": "translation_max_retries",
            "translation_retry_backoff_seconds": "translation_retry_backoff_seconds",
            "translation_llm_temperature": "translation_llm_temperature",
            "translation_llm_top_p": "translation_llm_top_p",
            "translation_llm_max_tokens": "translation_llm_max_tokens",
            "system_prompt": "system_prompt",
            "ui_language": "ui_language",
            "source_language": "source_language",
            "target_language": "target_language",
            "detect_model": "detect_model",
            "confidence_threshold": "confidence_threshold",
            "tiling_enabled": "tiling_enabled",
            "ocr_engine": "ocr_engine",
            "ocr_padding": "ocr_padding",
            "ocr_crop_scale": "ocr_crop_scale",
            "line_merge_sensitivity": "line_merge_sensitivity",
            "adaptive_binarization": "adaptive_binarization",
            "adaptive_binarization_strength": "adaptive_binarization_strength",
            "smart_direction": "smart_direction",
            "text_direction_override": "text_direction_override",
            "bubbles_only": "bubbles_only",
            "min_font_size": "min_font_size",
            "max_font_size": "max_font_size",
            "default_font_size": "default_font_size",
            "inpaint_engine": "inpaint_engine",
            "inpaint_mask_dilation": "inpaint_mask_dilation",
            "inpaint_use_textbox_only": "inpaint_use_textbox_only",
            "inpaint_clip_to_bubble": "inpaint_clip_to_bubble",
            "setup_completed": "setup_completed",
        },
    )

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def load(self) -> None:
        """Load settings from *SETTINGS_FILE_PATH* (if it exists)."""
        if not os.path.exists(SETTINGS_FILE_PATH):
            return

        try:
            with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
        except Exception:
            logger.exception("Failed to read settings from %s", SETTINGS_FILE_PATH)
            return

        for json_key, field_name in self._FIELD_MAP.items():
            value = data.get(json_key)
            if value is None:
                continue
            # Legacy migrations
            if field_name == "translation_provider" and value == "argos":
                value = "google"
            if field_name == "detect_model" and value == "Small (INT8) [기본값]":
                value = "High Precision (FP32)"
            if field_name == "ocr_engine" and value in {"auto", "high_precision", "high-quality", "high_quality", "quality"}:
                value = "balanced"
            if field_name == "inpaint_engine" and value in {"aot", "high_precision", "high-quality", "high_quality", "quality"}:
                value = "lama"
            if field_name == "confidence_threshold" and value == 0.30:
                value = 0.45
            setattr(self, field_name, value)

        if "setup_completed" not in data:
            self.setup_completed = True

        logger.info("Settings loaded from %s", SETTINGS_FILE_PATH)

    def save(self) -> bool:
        """Persist current settings to *SETTINGS_FILE_PATH*."""
        data = {json_key: getattr(self, field_name)
                for json_key, field_name in self._FIELD_MAP.items()}
        try:
            with open(SETTINGS_FILE_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=4, ensure_ascii=False)
            logger.info("Settings saved to %s", SETTINGS_FILE_PATH)
            return True
        except Exception:
            logger.exception("Failed to save settings to %s", SETTINGS_FILE_PATH)
            return False

    # -----------------------------------------------------------------------
    # Legacy alias functions (keep old call sites working)
    # -----------------------------------------------------------------------

    @staticmethod
    def apply_adaptive_binarization(crop: np.ndarray) -> np.ndarray:
        """Apply adaptive thresholding to an image crop to isolate text lines.

        Pipeline: RGB→Gray → CLAHe contrast enhancement → adaptive binarization.
        CLAHe (Contrast Limited Adaptive Histogram Equalization) boosts local
        contrast so small / low-contrast Japanese kanas are more readable for
        the OCR engine.
        """
        if crop is None or crop.size == 0:
            return crop
        try:
            if len(crop.shape) == 3:
                if crop.shape[2] == 3:
                    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
                elif crop.shape[2] == 4:
                    gray = cv2.cvtColor(crop, cv2.COLOR_RGBA2GRAY)
                else:
                    gray = crop
            else:
                gray = crop

            clip_limit = float(getattr(config, "adaptive_binarization_strength", 2.0))
            clip_limit = max(0.5, min(5.0, clip_limit))
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            thresh = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            return cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB)
        except Exception:
            logger.exception("Adaptive binarization failed")
            return crop


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

config: AppConfig = AppConfig()

# Auto-load on import (preserves existing behaviour)
config.load()

# ---------------------------------------------------------------------------
# Legacy top-level aliases (backward compat — deprecated)
# These are kept so that code doing `app_config.TRANSLATION_MODEL` still
# works via `__getattr__` on the module level (see below).
# ---------------------------------------------------------------------------


def __getattr__(name: str) -> Any:
    """Fallback: redirect bare-name access to the singleton instance."""
    if name in ("TRANSLATION_MODEL", "TRANSLATION_PROVIDER",
                "TRANSLATION_API_BASE_URL", "TRANSLATION_API_KEY",
                "TRANSLATION_TIMEOUT_SECONDS", "TRANSLATION_SUPPORTS_VISION",
                "TRANSLATION_CACHE_ENABLED", "TRANSLATION_CACHE_MODE",
                "SYSTEM_PROMPT",
                "UI_LANGUAGE", "SOURCE_LANGUAGE", "TARGET_LANGUAGE",
                "DETECT_MODEL", "CONFIDENCE_THRESHOLD",
                "TILING_ENABLED", "BUBBLES_ONLY",
                "OCR_ENGINE", "OCR_PADDING", "OCR_CROP_SCALE", "LINE_MERGE_SENSITIVITY",
                "ADAPTIVE_BINARIZATION", "ADAPTIVE_BINARIZATION_STRENGTH",
                "SMART_DIRECTION", "TEXT_DIRECTION_OVERRIDE",
                "MIN_FONT_SIZE", "MAX_FONT_SIZE", "DEFAULT_FONT_SIZE",
                "INPAINT_MASK_DILATION", "INPAINT_USE_TEXTBOX_ONLY",
                "INPAINT_CLIP_TO_BUBBLE"):
        # Map SCREAMING_SNAKE_CASE → snake_case on the config instance
        snake = name.lower()
        if hasattr(config, snake):
            return getattr(config, snake)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Also expose the old function names for backward compatibility.
load_settings = config.load
save_settings = config.save
apply_adaptive_binarization = config.apply_adaptive_binarization
