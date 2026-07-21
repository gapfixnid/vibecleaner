from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

from .version import __version__ as APP_VERSION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants (never change at runtime)
# ---------------------------------------------------------------------------

OLLAMA_API_URL = "http://127.0.0.1:11434"
SETTINGS_FORMAT = "vibecleaner-settings"
SETTINGS_SCHEMA_VERSION = 2
SETTINGS_SCHEMA_VERSION_KEY = "schema_version"
LEGACY_SETTINGS_SCHEMA_VERSION_KEY = "settings_schema_version"


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
    show_detection_overlay: bool = False
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


def config_value(config: Any, name: str) -> Any:
    """Read a settings attribute, falling back to the AppConfig default.

    Keeps AppConfig the single source of default values: callers that hold a
    partial/fake config (tests) or no config at all still get the canonical
    default instead of a locally duplicated literal.
    """
    default = AppConfig.__dataclass_fields__[name].default
    return getattr(config, name, default)


# ---------------------------------------------------------------------------
# AppConfig — mutable settings container
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
    show_detection_overlay: bool = False

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

    # -- Persistence target (injected; not persisted) ------------------------
    settings_path: str | None = field(default=None, repr=False, compare=False)
    _settings_write_blocked: bool = field(default=False, init=False, repr=False, compare=False)
    _settings_unknown_fields: dict[str, Any] = field(default_factory=dict, init=False, repr=False, compare=False)

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
            "show_detection_overlay": "show_detection_overlay",
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
        """Load settings from ``self.settings_path`` (if set and it exists)."""
        if not self.settings_path or not os.path.exists(self.settings_path):
            return

        try:
            with open(self.settings_path, "r", encoding="utf-8") as fh:
                data: Any = json.load(fh)
        except Exception:
            logger.exception("Failed to read settings from %s", self.settings_path)
            self._settings_write_blocked = True
            return
        if not isinstance(data, dict):
            logger.error("Cannot load settings from %s: root value must be an object", self.settings_path)
            self._settings_write_blocked = True
            return

        settings_format = data.get("format")
        if settings_format is not None and settings_format != SETTINGS_FORMAT:
            logger.error("Cannot load settings from %s: unsupported format=%r", self.settings_path, settings_format)
            self._settings_write_blocked = True
            return

        schema_version = data.get(
            SETTINGS_SCHEMA_VERSION_KEY,
            data.get(LEGACY_SETTINGS_SCHEMA_VERSION_KEY, 0),
        )
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version < 0:
            logger.error(
                "Cannot load settings from %s: invalid %s=%r",
                self.settings_path,
                SETTINGS_SCHEMA_VERSION_KEY,
                schema_version,
            )
            self._settings_write_blocked = True
            return
        if schema_version > SETTINGS_SCHEMA_VERSION:
            logger.error(
                "Cannot load settings from %s: schema version %s is newer than supported version %s",
                self.settings_path,
                schema_version,
                SETTINGS_SCHEMA_VERSION,
            )
            # Do not allow a later save to replace settings written by a newer
            # application version with this version's incomplete schema.
            self._settings_write_blocked = True
            return

        data = self._migrate_settings(data, schema_version)
        self._settings_write_blocked = False
        metadata_keys = {
            "format",
            SETTINGS_SCHEMA_VERSION_KEY,
            LEGACY_SETTINGS_SCHEMA_VERSION_KEY,
            "app_version",
        }
        self._settings_unknown_fields = {
            key: value
            for key, value in data.items()
            if key not in self._FIELD_MAP and key not in metadata_keys
        }

        for json_key, field_name in self._FIELD_MAP.items():
            value = data.get(json_key)
            if value is None:
                continue
            setattr(self, field_name, value)

        logger.info("Settings loaded from %s", self.settings_path)

    @staticmethod
    def _migrate_settings(data: dict[str, Any], schema_version: int) -> dict[str, Any]:
        """Return settings upgraded to the current in-memory schema.

        Version 0 is the unversioned settings format used before Phase A.
        Migration is deliberately non-destructive: the source file is only
        rewritten when the normal settings save path runs.
        """
        migrated = dict(data)
        migrated.pop("pipeline_v2_enabled", None)
        migrated.pop("pipeline_v2_shadow", None)
        if schema_version == 0:
            migrated.setdefault("setup_completed", True)
            if migrated.get("translation_provider") == "argos":
                migrated["translation_provider"] = "google"
            if migrated.get("detect_model") == "Small (INT8) [기본값]":
                migrated["detect_model"] = "High Precision (FP32)"
            if migrated.get("ocr_engine") in {
                "auto", "high_precision", "high-quality", "high_quality", "quality"
            }:
                migrated["ocr_engine"] = "balanced"
            if migrated.get("inpaint_engine") in {
                "aot", "high_precision", "high-quality", "high_quality", "quality"
            }:
                migrated["inpaint_engine"] = "lama"
            if migrated.get("confidence_threshold") == 0.30:
                migrated["confidence_threshold"] = 0.45
        if schema_version < 2:
            if str(migrated.get("ocr_engine", "")).strip().lower() in {
                "fast", "speed", "paddleocr", "paddle_ocr"
            }:
                migrated["ocr_engine"] = "ppocr"
        migrated["format"] = SETTINGS_FORMAT
        migrated[SETTINGS_SCHEMA_VERSION_KEY] = SETTINGS_SCHEMA_VERSION
        migrated.setdefault("app_version", "unknown")
        migrated.pop(LEGACY_SETTINGS_SCHEMA_VERSION_KEY, None)
        return migrated

    def save(self) -> bool:
        """Persist current settings to ``self.settings_path``."""
        if not self.settings_path:
            logger.error("Cannot save settings: no settings_path configured")
            return False
        if self._settings_write_blocked:
            logger.error(
                "Cannot save settings to %s after loading an unsupported schema",
                self.settings_path,
            )
            return False

        data = {
            **self._settings_unknown_fields,
            "format": SETTINGS_FORMAT,
            SETTINGS_SCHEMA_VERSION_KEY: SETTINGS_SCHEMA_VERSION,
            "app_version": APP_VERSION,
            **{
                json_key: getattr(self, field_name)
                for json_key, field_name in self._FIELD_MAP.items()
            },
        }
        try:
            parent_dir = os.path.dirname(self.settings_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            fd, temporary_path = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=parent_dir or ".")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=4, ensure_ascii=False)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(temporary_path, self.settings_path)
            except Exception:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass
                raise
            logger.info("Settings saved to %s", self.settings_path)
            return True
        except Exception:
            logger.exception("Failed to save settings to %s", self.settings_path)
            return False
