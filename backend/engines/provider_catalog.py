"""Compatibility manifests for the engines used by the current v1 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.providers import (
    ConfigFieldSpec,
    ProviderCapabilities,
    ProviderManifest,
    ProviderModelProfile,
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


def _translation_manifest(
    provider: str,
    display_name: str,
    *,
    execution_modes: set[str],
    features: set[str],
    config_schema: tuple[ConfigFieldSpec, ...] = (),
    description: str = "",
    catalog_order: int,
) -> ProviderManifest:
    provider_id = f"builtin.translation.{provider.replace('_', '-')}"
    resources = {"cpu"} if execution_modes == {"local"} else {"cpu", "network"}
    return ProviderManifest(
        provider_id=provider_id,
        display_name=display_name,
        stage="translation",
        api_version="1",
        implementation_version=APP_VERSION,
        capabilities=ProviderCapabilities(
            languages={"en", "ja", "ko", "zh"},
            devices={"cpu"},
            execution_modes=execution_modes,
            features={"text", *features},
            supports_batch=True,
        ),
        resource_classes=resources,
        max_concurrency=1,
        queue_capacity=8,
        config_schema=config_schema,
        legacy_adapter=True,
        selection_value=provider,
        description=description,
        catalog_order=catalog_order,
    )


def _translation_manifests() -> tuple[ProviderManifest, ...]:
    api_key = lambda label, placeholder=None, help_text=None: ConfigFieldSpec(
        key="translation_api_key",
        value_type="secret",
        label=label,
        placeholder=placeholder,
        help_text=help_text,
    )
    model = ConfigFieldSpec(
        key="translation_model",
        value_type="model",
        label="settings.model",
        default="",
    )
    return (
        _translation_manifest(
            "google",
            "Google Translate",
            execution_modes={"remote"},
            features=set(),
            description="settings.googleProviderInfo",
            catalog_order=10,
        ),
        _translation_manifest(
            "deepl",
            "DeepL Translation API",
            execution_modes={"remote"},
            features=set(),
            config_schema=(
                api_key(
                    "settings.deeplApiKey",
                    "settings.deeplApiKeyPlaceholder",
                    "settings.deeplApiKeyHelp",
                ),
            ),
            catalog_order=20,
        ),
        _translation_manifest(
            "openai",
            "OpenAI",
            execution_modes={"remote"},
            features={"context", "llm-options", "model-picker", "model-requires-key", "vision-context", "system-prompt"},
            config_schema=(api_key("settings.openaiApiKey", "sk-proj-..."), model),
            catalog_order=30,
        ),
        _translation_manifest(
            "claude",
            "Anthropic Claude",
            execution_modes={"remote"},
            features={"context", "llm-options", "model-picker", "model-requires-key", "vision-context", "system-prompt"},
            config_schema=(api_key("settings.claudeApiKey", "sk-ant-..."), model),
            catalog_order=40,
        ),
        _translation_manifest(
            "papago",
            "Naver Papago API",
            execution_modes={"remote"},
            features=set(),
            config_schema=(
                ConfigFieldSpec(
                    key="translation_api_base_url",
                    value_type="string",
                    label="settings.papagoClientId",
                    placeholder="settings.papagoClientIdPlaceholder",
                ),
                api_key("settings.papagoClientSecret", "settings.papagoClientSecretPlaceholder"),
            ),
            catalog_order=50,
        ),
        _translation_manifest(
            "baidu",
            "Baidu Fanyi API",
            execution_modes={"remote"},
            features=set(),
            config_schema=(
                ConfigFieldSpec(
                    key="translation_api_base_url",
                    value_type="string",
                    label="settings.baiduAppId",
                    placeholder="settings.baiduAppIdPlaceholder",
                ),
                api_key("settings.baiduSecretKey", "settings.baiduSecretKeyPlaceholder"),
            ),
            catalog_order=60,
        ),
        _translation_manifest(
            "ollama",
            "Ollama",
            execution_modes={"local"},
            features={"context", "llm-options", "model-picker", "vision-context", "system-prompt"},
            config_schema=(model,),
            description="settings.ollamaProviderInfo",
            catalog_order=70,
        ),
        _translation_manifest(
            "openai_compatible",
            "OpenAI Compatible",
            execution_modes={"local", "remote"},
            features={"context", "llm-options", "model-picker", "manual-model", "vision-context", "system-prompt"},
            config_schema=(
                ConfigFieldSpec(
                    key="translation_api_base_url",
                    value_type="string",
                    label="settings.apiBaseUrl",
                    placeholder="http://localhost:1234/v1",
                ),
                model,
                api_key("settings.apiKeyOptional", "settings.optionalApiKeyPlaceholder"),
            ),
            catalog_order=80,
        ),
    )


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
            model_catalog=(
                ProviderModelProfile("High Precision (FP32)", "High Precision (FP32)", 0.95, 0.45, frozenset({"cpu", "gpu"})),
                ProviderModelProfile("Small (INT8)", "Small (INT8)", 0.75, 0.90, frozenset({"cpu"})),
            ),
            queue_capacity=2,
            config_schema=(
                ConfigFieldSpec(
                    key="detect_model",
                    value_type="enum",
                    label="settings.detectionModel",
                    default="High Precision (FP32)",
                    choices=("High Precision (FP32)", "Small (INT8)"),
                    choice_labels=("settings.modelHighPrecision", "settings.modelSmall"),
                ),
                ConfigFieldSpec(
                    key="confidence_threshold",
                    value_type="number",
                    label="settings.confidenceThreshold",
                    default=0.45,
                    minimum=0.1,
                    maximum=0.9,
                    step=0.05,
                ),
                ConfigFieldSpec(
                    key="tiling_enabled",
                    value_type="boolean",
                    label="settings.tilingEnabled",
                    default=True,
                ),
                ConfigFieldSpec(
                    key="bubbles_only",
                    value_type="boolean",
                    label="settings.bubblesOnly",
                    default=False,
                ),
                ConfigFieldSpec(
                    key="show_detection_overlay",
                    value_type="boolean",
                    label="settings.showDetectionOverlay",
                    default=False,
                    advanced=True,
                ),
                ConfigFieldSpec(
                    key="smart_direction",
                    value_type="boolean",
                    label="settings.smartDirection",
                    default=True,
                ),
                ConfigFieldSpec(
                    key="text_direction_override",
                    value_type="enum",
                    label="settings.directionOverride",
                    default="auto",
                    choices=("auto", "horizontal", "vertical"),
                    choice_labels=(
                        "settings.directionAuto",
                        "settings.directionHorizontal",
                        "settings.directionVertical",
                    ),
                ),
                ConfigFieldSpec(
                    key="line_merge_sensitivity",
                    value_type="number",
                    label="settings.lineMergeSensitivity",
                    default=1.2,
                    minimum=0.5,
                    maximum=2.5,
                    step=0.1,
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
            model_catalog=(
                ProviderModelProfile("balanced", "Automatic OCR", 0.90, 0.70, frozenset({"cpu", "gpu", "io"})),
                ProviderModelProfile("manga_ocr", "Manga OCR Mobile ONNX", 0.92, 0.55, frozenset({"cpu", "gpu", "io"})),
                ProviderModelProfile("ppocr", "PP-OCRv6 Medium Recognition ONNX", 0.88, 0.85, frozenset({"cpu", "gpu", "io"})),
            ),
            queue_capacity=4,
            config_schema=(
                ConfigFieldSpec(
                    key="ocr_engine",
                    value_type="enum",
                    label="settings.ocrEngine",
                    default="balanced",
                    choices=("balanced", "manga_ocr", "ppocr"),
                    choice_labels=(
                        "settings.ocrEngineBalanced",
                        "settings.ocrEngineManga",
                        "settings.ocrEnginePpocr",
                    ),
                ),
                ConfigFieldSpec(
                    key="ocr_padding",
                    value_type="integer",
                    label="settings.ocrPadding",
                    default=8,
                    minimum=0,
                    maximum=32,
                    step=1,
                ),
                ConfigFieldSpec(
                    key="ocr_crop_scale",
                    value_type="number",
                    label="settings.ocrCropScale",
                    default=1.5,
                    minimum=0.5,
                    maximum=3.0,
                    step=0.25,
                ),
                ConfigFieldSpec(
                    key="adaptive_binarization",
                    value_type="boolean",
                    label="settings.adaptiveBinarization",
                    default=True,
                ),
                ConfigFieldSpec(
                    key="adaptive_binarization_strength",
                    value_type="number",
                    label="settings.adaptiveBinarizationStrength",
                    default=2.0,
                    minimum=0.5,
                    maximum=5.0,
                    step=0.25,
                    visible_when_key="adaptive_binarization",
                    visible_when_value=True,
                ),
            ),
            legacy_adapter=True,
        ),
        _legacy("builtin.ocr.local", detection_service),
    )
    for manifest in _translation_manifests():
        registry.register(manifest, _legacy(manifest.provider_id, translation_service))
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
            model_catalog=(
                ProviderModelProfile("lama", "LaMa", 0.92, 0.45, frozenset({"cpu", "gpu"})),
                ProviderModelProfile("opencv", "OpenCV Telea", 0.68, 0.95, frozenset({"cpu"})),
            ),
            queue_capacity=2,
            config_schema=(
                ConfigFieldSpec(
                    key="inpaint_engine",
                    value_type="enum",
                    label="settings.inpaintEngine",
                    default="lama",
                    choices=("lama", "opencv"),
                    choice_labels=("settings.inpaintingEngineBalanced", "settings.inpaintingEngineFast"),
                ),
                ConfigFieldSpec(
                    key="inpaint_mask_dilation",
                    value_type="integer",
                    label="settings.maskDilation",
                    default=2,
                    minimum=0,
                    maximum=10,
                    step=1,
                ),
                ConfigFieldSpec(
                    key="inpaint_use_textbox_only",
                    value_type="boolean",
                    label="settings.cleanTextboxOnly",
                    default=True,
                ),
                ConfigFieldSpec(
                    key="inpaint_clip_to_bubble",
                    value_type="boolean",
                    label="settings.clipInpaintingMask",
                    default=True,
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
