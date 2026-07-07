from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AppConfigSnapshot:
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
    ui_language: str = "en"
    source_language: str = "Japanese"
    target_language: str = "Korean"
    detect_model: str = "High Precision (FP32)"
    confidence_threshold: float = 0.45
    tiling_enabled: bool = True
    bubbles_only: bool = False
    ocr_engine: str = "balanced"
    ocr_padding: int = 8
    ocr_crop_scale: float = 1.5
    line_merge_sensitivity: float = 1.2
    adaptive_binarization: bool = True
    adaptive_binarization_strength: float = 2.0
    smart_direction: bool = True
    text_direction_override: str = "auto"
    min_font_size: float = 6.0
    max_font_size: float = 48.0
    default_font_size: float = 18.0
    inpaint_engine: str = "lama"
    inpaint_mask_dilation: int = 2
    inpaint_use_textbox_only: bool = True
    inpaint_clip_to_bubble: bool = True
    setup_completed: bool = False

    @classmethod
    def from_object(cls, source: Any) -> "AppConfigSnapshot":
        values = {
            field: getattr(source, field)
            for field in cls.__dataclass_fields__
            if hasattr(source, field)
        }
        return cls(**values)
