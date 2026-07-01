# modules/config.py
# Centralized application configuration.
#
# Usage:
#   from modules.config import config          # AppConfig singleton

from __future__ import annotations
import logging
import os
import platform
from dataclasses import dataclass
import cv2
import numpy as np
from app.version import APP_NAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants (never change at runtime)
# ---------------------------------------------------------------------------
OLLAMA_API_URL = "http://127.0.0.1:11434"

def _get_app_data_dir() -> str:
    if platform.system() == "Windows":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base_dir, APP_NAME)
    if platform.system() == "Darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    return os.path.expanduser(f"~/.config/{APP_NAME}")

APP_DATA_DIR: str = _get_app_data_dir()
os.makedirs(APP_DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# AppConfig — mutable settings container (single instance: `config`)
# ---------------------------------------------------------------------------

@dataclass
class AppConfig:
    # -- Translation --------------------------------------------------------
    translation_model: str = ""
    translation_timeout_seconds: int = 90
    translation_supports_vision: bool = False
    translation_cache_enabled: bool = True
    translation_cache_mode: str = "text_with_context"
    system_prompt: str = ""

    # -- Languages ----------------------------------------------------------
    source_language: str = "Japanese"
    target_language: str = "Korean"

    # -- Detection ----------------------------------------------------------
    detect_model: str = "High Precision (FP32)"
    confidence_threshold: float = 0.45
    tiling_enabled: bool = True
    bubbles_only: bool = False

    # -- OCR ----------------------------------------------------------------
    ocr_padding: int = 8
    line_merge_sensitivity: float = 1.2
    adaptive_binarization: bool = True
    smart_direction: bool = True

    # -- Rendering ----------------------------------------------------------
    min_font_size: float = 6.0
    max_font_size: float = 48.0
    default_font_size: float = 18.0

    # -- Inpainting ---------------------------------------------------------
    inpaint_mask_dilation: int = 2
    inpaint_use_textbox_only: bool = True
    inpaint_clip_to_bubble: bool = True

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

    @staticmethod
    def apply_adaptive_binarization(crop: np.ndarray) -> np.ndarray:
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

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
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

def __getattr__(name: str):
    snake = name.lower()
    if hasattr(config, snake):
        return getattr(config, snake)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
