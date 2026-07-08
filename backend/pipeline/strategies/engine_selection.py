from __future__ import annotations

from core.config import AppConfigSnapshot
from core.ports.detection import DetectionOptions
from core.ports.inpainting import InpaintOptions
from core.ports.ocr import OcrOptions
from core.ports.rendering import RenderOptions
from core.ports.translation import TranslationOptions


class EngineSelectionStrategy:
    def detection_options(self, settings: AppConfigSnapshot) -> DetectionOptions:
        return DetectionOptions(
            model_name=settings.detect_model,
            confidence_threshold=settings.confidence_threshold,
            tiling_enabled=settings.tiling_enabled,
            bubbles_only=settings.bubbles_only,
            line_merge_sensitivity=settings.line_merge_sensitivity,
            smart_direction=settings.smart_direction,
            text_direction_override=settings.text_direction_override,
        )

    def ocr_options(self, settings: AppConfigSnapshot) -> OcrOptions:
        return OcrOptions(
            engine=settings.ocr_engine,
            padding=settings.ocr_padding,
            crop_scale=settings.ocr_crop_scale,
            adaptive_binarization=settings.adaptive_binarization,
            adaptive_binarization_strength=settings.adaptive_binarization_strength,
        )

    def translation_options(self, settings: AppConfigSnapshot) -> TranslationOptions:
        return TranslationOptions(
            provider=settings.translation_provider,
            source_language=settings.source_language,
            target_language=settings.target_language,
            model=settings.translation_model,
        )

    def inpaint_options(self, settings: AppConfigSnapshot) -> InpaintOptions:
        return InpaintOptions(
            engine=settings.inpaint_engine,
            mask_dilation=settings.inpaint_mask_dilation,
            clip_to_bubble=settings.inpaint_clip_to_bubble,
        )

    def render_options(self, settings: AppConfigSnapshot) -> RenderOptions:
        return RenderOptions(
            min_font_size=settings.min_font_size,
            max_font_size=settings.max_font_size,
            default_font_size=settings.default_font_size,
        )
