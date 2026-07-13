"""Compatibility manifests for the engines used by the current v1 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.providers import (
    ConfigFieldSpec,
    ProviderCapabilities,
    ProviderManifest,
    ProviderRegistry,
)
from ..core.version import __version__ as APP_VERSION


@dataclass
class LegacyProviderAdapter:
    """Lifecycle wrapper used until a service implements its stage port directly."""

    provider_id: str
    service: Any

    def prepare(self, runtime: Any = None) -> None:
        return None

    def shutdown(self) -> None:
        shutdown = getattr(self.service, "shutdown", None)
        if callable(shutdown):
            shutdown()


def _legacy(provider_id: str, service: Any) -> LegacyProviderAdapter:
    return LegacyProviderAdapter(provider_id=provider_id, service=service)


def register_builtin_providers(
    registry: ProviderRegistry,
    *,
    detection_service: Any,
    translation_service: Any,
    inpainting_service: Any,
    render_service: Any,
) -> None:
    """Expose existing service facades behind stable compatibility manifests.

    The v1 detection service currently owns both detection and OCR, so the two
    manifests intentionally point at the same adapter until Phase C separates
    their execution contracts.
    """
    registry.register(
        ProviderManifest(
            provider_id="builtin.detection.rtdetr-v2",
            display_name="RT-DETR v2 Detection",
            stage="detection",
            api_version="1",
            implementation_version=APP_VERSION,
            capabilities=ProviderCapabilities(
                devices={"cpu", "gpu"},
                execution_modes={"local"},
                features={"regions", "confidence", "tiling"},
            ),
            resource_classes={"cpu", "gpu"},
            config_schema=(
                ConfigFieldSpec(
                    key="detect_model",
                    value_type="enum",
                    label="settings.detectionModel",
                    default="High Precision (FP32)",
                    choices=("High Precision (FP32)", "Small (INT8)"),
                ),
                ConfigFieldSpec(
                    key="confidence_threshold",
                    value_type="number",
                    label="settings.confidenceThreshold",
                    default=0.45,
                ),
                ConfigFieldSpec(
                    key="tiling_enabled",
                    value_type="boolean",
                    label="settings.tilingEnabled",
                    default=True,
                ),
            ),
            legacy_adapter=True,
        ),
        _legacy("builtin.detection.rtdetr-v2", detection_service),
    )
    registry.register(
        ProviderManifest(
            provider_id="builtin.ocr.local",
            display_name="Local OCR",
            stage="ocr",
            api_version="1",
            implementation_version=APP_VERSION,
            capabilities=ProviderCapabilities(
                languages={"en", "ja", "ko", "zh"},
                devices={"cpu", "gpu"},
                execution_modes={"local"},
                features={"text", "vertical-text", "persistent-cache"},
                supports_batch=True,
            ),
            resource_classes={"cpu", "gpu", "io"},
            config_schema=(
                ConfigFieldSpec(
                    key="ocr_engine",
                    value_type="enum",
                    label="settings.ocrEngine",
                    default="balanced",
                    choices=("balanced", "fast"),
                ),
                ConfigFieldSpec(
                    key="ocr_padding",
                    value_type="integer",
                    label="settings.ocrPadding",
                    default=8,
                ),
                ConfigFieldSpec(
                    key="ocr_crop_scale",
                    value_type="number",
                    label="settings.ocrCropScale",
                    default=1.5,
                ),
            ),
            legacy_adapter=True,
        ),
        _legacy("builtin.ocr.local", detection_service),
    )
    registry.register(
        ProviderManifest(
            provider_id="builtin.translation.configured",
            display_name="Configured Translation Provider",
            stage="translation",
            api_version="1",
            implementation_version=APP_VERSION,
            capabilities=ProviderCapabilities(
                languages={"en", "ja", "ko", "zh"},
                devices={"cpu"},
                execution_modes={"local", "remote"},
                features={"text", "configurable-provider", "context"},
                supports_batch=True,
            ),
            resource_classes={"cpu", "network"},
            max_concurrency=1,
            config_schema=(
                ConfigFieldSpec(
                    key="translation_provider",
                    value_type="enum",
                    label="settings.translationProvider",
                    default="google",
                    choices=(
                        "google", "deepl", "openai", "claude", "papago",
                        "baidu", "ollama", "openai_compatible",
                    ),
                ),
                ConfigFieldSpec(
                    key="translation_model",
                    value_type="string",
                    label="settings.model",
                    default="",
                ),
                ConfigFieldSpec(
                    key="translation_api_base_url",
                    value_type="string",
                    label="settings.apiBaseUrl",
                    default="",
                ),
                ConfigFieldSpec(
                    key="translation_api_key",
                    value_type="secret",
                    label="settings.apiKeyOptional",
                ),
            ),
            legacy_adapter=True,
        ),
        _legacy("builtin.translation.configured", translation_service),
    )
    registry.register(
        ProviderManifest(
            provider_id="builtin.inpainting.hybrid",
            display_name="Hybrid Inpainting",
            stage="inpainting",
            api_version="1",
            implementation_version=APP_VERSION,
            capabilities=ProviderCapabilities(
                devices={"cpu", "gpu"},
                execution_modes={"local"},
                features={"mask", "edge-protection", "bubble-clipping"},
                supports_batch=True,
            ),
            resource_classes={"cpu", "gpu"},
            config_schema=(
                ConfigFieldSpec(
                    key="inpaint_engine",
                    value_type="enum",
                    label="settings.inpaintEngine",
                    default="lama",
                    choices=("lama", "opencv"),
                ),
                ConfigFieldSpec(
                    key="inpaint_mask_dilation",
                    value_type="integer",
                    label="settings.maskDilation",
                    default=2,
                ),
            ),
            legacy_adapter=True,
        ),
        _legacy("builtin.inpainting.hybrid", inpainting_service),
    )
    registry.register(
        ProviderManifest(
            provider_id="builtin.rendering.qt",
            display_name="Qt Text Renderer",
            stage="rendering",
            api_version="1",
            implementation_version=APP_VERSION,
            capabilities=ProviderCapabilities(
                languages={"en", "ja", "ko", "zh"},
                devices={"cpu"},
                execution_modes={"local"},
                features={"text-layout", "font-fallback", "bubble-mask"},
                supports_batch=True,
            ),
            resource_classes={"cpu"},
            config_schema=(
                ConfigFieldSpec(
                    key="min_font_size",
                    value_type="number",
                    label="settings.minFontSize",
                    default=6.0,
                ),
                ConfigFieldSpec(
                    key="max_font_size",
                    value_type="number",
                    label="settings.maxFontSize",
                    default=48.0,
                ),
            ),
            legacy_adapter=True,
        ),
        _legacy("builtin.rendering.qt", render_service),
    )
