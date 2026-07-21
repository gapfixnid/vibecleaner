from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from ..core.errors import PageNotFoundError
from ..core.models.image import ImageData
from ..infrastructure.job_messages import msg_from_context
from .page_analysis import (
    bubbles_from_analysis,
    merge_overlapping_bubbles,
    bubble_clip_boxes,
    bubble_source_polygons,
    inpaint_boxes,
    recover_missing_source_polygons,
)
from .context import PipelineContext
from .registry import StageRegistry
from .runner import PipelineRunner
from .quality import AdaptiveQualityRouter

logger = logging.getLogger(__name__)


def _is_suspicious_ocr_text(text: object) -> bool:
    return len(str(text or "").strip()) <= 2


def _is_better_ocr_text(original: object, candidate: object) -> bool:
    original_text = str(original or "").strip()
    candidate_text = str(candidate or "").strip()
    if not candidate_text:
        return False
    if not original_text:
        return True
    return len(candidate_text) > len(original_text)


def _resolve_page_index(state: Any, page_id: str) -> int:
    if page_id.isdigit():
        idx = int(page_id)
        if 0 <= idx < len(state.pages):
            return idx
        raise PageNotFoundError(page_id)
    for idx, page in enumerate(state.pages):
        if page.page_id == page_id:
            return idx
    raise PageNotFoundError(page_id)


def _ensure_project_revision(state: Any, start_revision: int) -> None:
    if state.revision != start_revision:
        raise RuntimeError("Project changed while the operation was running. Please retry.")


class PageDetectionStage:
    name = "detection"

    def __init__(self, detection_service: Any, *, ensure_page_image: Any, quality_router: Any | None = None, provider_manifest: Any | None = None) -> None:
        self.detection_service = detection_service
        self.ensure_page_image = ensure_page_image
        self.quality_router = quality_router or AdaptiveQualityRouter()
        self.provider_manifest = provider_manifest

    def run(self, context: PipelineContext) -> PipelineContext:
        state = context.artifacts["state"]
        job = context.artifacts["job"]
        job_manager = context.artifacts["job_manager"]
        show_progress = context.artifacts["show_progress"]
        config = context.artifacts["config"]

        with state.lock:
            page_idx = _resolve_page_index(state, context.page_id)
            page = state.pages[page_idx]
            self.ensure_page_image(page)
            start_revision = state.revision
            image = page.cv_image.copy()
            inpainted_image = page.inpainted_image.copy() if page.inpainted_image is not None else None
            local_bubbles = [bubble.clone() for bubble in page.bubbles]
            bubble_counter = page.bubble_counter

        context.page = page
        context.image = ImageData(
            array=image,
            mode="BGR",
            explicit_width=image.shape[1],
            explicit_height=image.shape[0],
        )
        context.artifacts.update(
            {
                "page_idx": page_idx,
                "start_revision": start_revision,
                "image": image,
                "inpainted_image": inpainted_image,
                "local_bubbles": local_bubbles,
                "bubble_counter": bubble_counter,
                "blocks": [],
            }
        )

        job_manager.ensure_not_cancelled(job)
        if not local_bubbles:
            if show_progress:
                job_manager.update(job, progress=15, message=msg_from_context("page_translation.detecting", context))
            if getattr(context, "pipeline_variant", None) == "v2" and hasattr(
                self.detection_service, "detect_only"
            ):
                blocks = self.detection_service.detect_only(image)
                detection_score = self.quality_router.evaluate_detection(blocks)
                selected_model = self.quality_router.select_model(
                    "detection", config.detect_model, detection_score, self.provider_manifest
                )
                if (
                    not detection_score.passed
                    and selected_model != config.detect_model
                ):
                    blocks = self.detection_service.detect_only(
                        image, model_name=selected_model
                    )
                    detection_score = self.quality_router.evaluate_detection(blocks)
                    context.artifacts.setdefault("quality_replans", []).append(
                        {"stage": "detection", "model": selected_model}
                    )
                context.artifacts["blocks"] = blocks
                context.artifacts["ocr_pending"] = True
                context.artifacts.setdefault("quality_scores", {})["detection"] = (
                    detection_score
                )
            else:
                context.artifacts["blocks"] = self.detection_service.detect_and_ocr(
                    image,
                    lang=config.source_language,
                )
            job_manager.ensure_not_cancelled(job)
        return context


class PageOcrStage:
    name = "ocr"

    def __init__(
        self,
        *,
        page_analysis_service: Any,
        bubble_analysis_service: Any,
        layout_planner_service: Any,
        detection_service: Any | None = None,
        quality_router: Any | None = None,
        provider_manifest: Any | None = None,
    ) -> None:
        self.page_analysis_service = page_analysis_service
        self.bubble_analysis_service = bubble_analysis_service
        self.layout_planner_service = layout_planner_service
        self.detection_service = detection_service
        self.quality_router = quality_router or AdaptiveQualityRouter()
        self.provider_manifest = provider_manifest

    def run(self, context: PipelineContext) -> PipelineContext:
        job = context.artifacts["job"]
        job_manager = context.artifacts["job_manager"]
        show_progress = context.artifacts["show_progress"]
        config = context.artifacts["config"]
        image = context.artifacts["image"]
        local_bubbles = context.artifacts["local_bubbles"]

        diagnostics_before = self._diagnostics()
        ocr_provenance = {
            "language": config.source_language,
            "engine": config.ocr_engine,
            "preprocessing": {
                "padding": int(getattr(config, "ocr_padding", 8)),
                "crop_scale": float(getattr(config, "ocr_crop_scale", 1.5)),
                "adaptive_binarization": bool(getattr(config, "adaptive_binarization", True)),
                "adaptive_binarization_strength": float(
                    getattr(config, "adaptive_binarization_strength", 2.0)
                ),
            },
            "cache": {
                "hits_before": diagnostics_before.get("ocr_cache_hits"),
                "misses_before": diagnostics_before.get("ocr_cache_misses"),
            },
            "skipped": bool(local_bubbles),
        }

        if not local_bubbles:
            if context.artifacts.pop("ocr_pending", False):
                if self.detection_service is None or not hasattr(
                    self.detection_service, "ocr_only"
                ):
                    raise RuntimeError("Pipeline v2 OCR adapter is not available")
                context.artifacts["blocks"] = self.detection_service.ocr_only(
                    image,
                    context.artifacts["blocks"],
                    lang=config.source_language,
                )
                ocr_score = self.quality_router.evaluate_ocr(
                    context.artifacts["blocks"], config.source_language
                )
                suspicious_blocks = [
                    block for block in context.artifacts["blocks"]
                    if _is_suspicious_ocr_text(getattr(block, "text", ""))
                ]
                if suspicious_blocks:
                    original_texts = {
                        id(block): getattr(block, "text", "") for block in suspicious_blocks
                    }
                    retry_padding = max(1, int(getattr(config, "ocr_padding", 8)) * 2)
                    retry_scale = max(1.0, float(getattr(config, "ocr_crop_scale", 1.5)) * 1.25)
                    retry_engine = config.ocr_engine
                    self.detection_service.ocr_only(
                        image,
                        suspicious_blocks,
                        lang=config.source_language,
                        engine=retry_engine,
                        padding=retry_padding,
                        crop_scale=retry_scale,
                        adaptive_binarization=True,
                        adaptive_binarization_strength=max(
                            1.0, float(getattr(config, "adaptive_binarization_strength", 2.0)) + 1.0
                        ),
                        use_cache=False,
                    )
                    recovered_blocks = 0
                    for block in suspicious_blocks:
                        original = original_texts[id(block)]
                        if _is_better_ocr_text(original, getattr(block, "text", "")):
                            recovered_blocks += 1
                        else:
                            block.text = original
                    ocr_score = self.quality_router.evaluate_ocr(
                        context.artifacts["blocks"], config.source_language
                    )
                    context.artifacts.setdefault("quality_replans", []).append({
                        "stage": "ocr", "model": retry_engine,
                        "profile": "suspicious_text_recovery", "recovered_blocks": recovered_blocks,
                        "candidate_blocks": len(suspicious_blocks),
                        "passed": ocr_score.passed,
                    })
                if not ocr_score.passed:
                    retry_engine = self.quality_router.select_model(
                        "ocr", config.ocr_engine, ocr_score, self.provider_manifest
                    )
                    retry_padding = max(1, int(getattr(config, "ocr_padding", 8)) * 2)
                    retry_scale = max(1.0, float(getattr(config, "ocr_crop_scale", 1.5)) * 1.25)
                    context.artifacts["blocks"] = self.detection_service.ocr_only(
                        image,
                        context.artifacts["blocks"],
                        lang=config.source_language,
                        engine=retry_engine,
                        padding=retry_padding,
                        crop_scale=retry_scale,
                        adaptive_binarization=True,
                        adaptive_binarization_strength=max(
                            1.0, float(getattr(config, "adaptive_binarization_strength", 2.0)) + 1.0
                        ),
                        use_cache=False,
                    )
                    ocr_score = self.quality_router.evaluate_ocr(
                        context.artifacts["blocks"], config.source_language
                    )
                    context.artifacts.setdefault("quality_replans", []).append({
                        "stage": "ocr", "model": retry_engine,
                        "profile": "enhanced_preprocessing", "passed": ocr_score.passed
                    })
                context.artifacts.setdefault("quality_scores", {})["ocr"] = ocr_score
            if show_progress:
                job_manager.update(job, progress=30, message=msg_from_context("page_translation.analyzing", context))
            local_bubbles = bubbles_from_analysis(
                image,
                context.artifacts["blocks"],
                config.source_language,
                config.target_language,
                config=config,
                page_analysis_service=self.page_analysis_service,
                bubble_analysis_service=self.bubble_analysis_service,
                layout_planner_service=self.layout_planner_service,
            )
            job_manager.ensure_not_cancelled(job)
            local_bubbles = merge_overlapping_bubbles(local_bubbles)
            for idx, bubble in enumerate(local_bubbles, 1):
                bubble.id = idx
            context.artifacts["bubble_counter"] = len(local_bubbles)

        context.artifacts["local_bubbles"] = local_bubbles
        context.artifacts["ocr_result"] = local_bubbles
        diagnostics_after = self._diagnostics()
        ocr_provenance["cache"].update({
            "hits_after": diagnostics_after.get("ocr_cache_hits"),
            "misses_after": diagnostics_after.get("ocr_cache_misses"),
        })
        raw_confidences = [
            float(value) for block in context.artifacts.get("blocks", [])
            if (value := getattr(block, "ocr_confidence", None)) is not None
        ]
        ocr_provenance["raw_confidence"] = {
            "available_count": len(raw_confidences),
            "mean": round(sum(raw_confidences) / len(raw_confidences), 4)
            if raw_confidences else None,
        }
        ocr_provenance["retry_count"] = sum(
            1 for item in context.artifacts.get("quality_replans", [])
            if item.get("stage") == "ocr"
        )
        context.artifacts["ocr_provenance"] = ocr_provenance
        return context

    def _diagnostics(self) -> dict[str, Any]:
        getter = getattr(self.detection_service, "get_diagnostics", None)
        if not callable(getter):
            return {}
        try:
            value = getter()
            return value if isinstance(value, dict) else {}
        except Exception:
            logger.debug("Unable to capture OCR diagnostics", exc_info=True)
            return {}


class PageTranslationStage:
    name = "translation"

    def __init__(self, translation_service: Any) -> None:
        self.translation_service = translation_service

    def run(self, context: PipelineContext) -> PipelineContext:
        job = context.artifacts["job"]
        job_manager = context.artifacts["job_manager"]
        show_progress = context.artifacts["show_progress"]
        config = context.artifacts["config"]
        image = context.artifacts["image"]
        local_bubbles = context.artifacts["local_bubbles"]
        untranslated = [bubble for bubble in local_bubbles if not bubble.translated]
        temp_blocks = []

        if untranslated:
            if show_progress:
                job_manager.update(job, progress=45, message=msg_from_context("page_translation.translating", context))
            temp_blocks = [
                SimpleNamespace(text_bbox=bubble.source_xyxy(), text=bubble.text, translation="")
                for bubble in untranslated
            ]
            self.translation_service.translate_blocks(temp_blocks, config.source_language, config.target_language, image)
            for bubble, text_block in zip(untranslated, temp_blocks):
                bubble.translated = text_block.translation
            job_manager.ensure_not_cancelled(job)

        context.artifacts["temp_blocks"] = temp_blocks
        context.artifacts["translation_result"] = local_bubbles
        return context


class PageInpaintingStage:
    name = "inpainting"

    def __init__(self, inpainting_service: Any, *, quality_router: Any | None = None, provider_manifest: Any | None = None) -> None:
        self.inpainting_service = inpainting_service
        self.quality_router = quality_router or AdaptiveQualityRouter()
        self.provider_manifest = provider_manifest

    def run(self, context: PipelineContext) -> PipelineContext:
        job = context.artifacts["job"]
        job_manager = context.artifacts["job_manager"]
        show_progress = context.artifacts["show_progress"]
        config = context.artifacts["config"]
        image = context.artifacts["image"]
        inpainted_image = context.artifacts["inpainted_image"]
        local_bubbles = context.artifacts["local_bubbles"]

        if inpainted_image is None:
            if show_progress:
                job_manager.update(job, progress=60, message=msg_from_context("page_translation.cleaning", context))
            recover_missing_source_polygons(
                image,
                local_bubbles,
                source_language=str(getattr(config, "source_language", "")),
            )
            boxes = inpaint_boxes(local_bubbles, use_textbox_only=config.inpaint_use_textbox_only)
            inpainted_image = self.inpainting_service.clean_background(
                image,
                boxes,
                bubble_clip_boxes(local_bubbles),
                source_polygons=bubble_source_polygons(local_bubbles),
                protect_edges=True,
            )
            job_manager.ensure_not_cancelled(job)

            quality_score = self.quality_router.evaluate_inpainting(image, inpainted_image, boxes)
            if not quality_score.passed:
                current_engine = str(getattr(config, "inpaint_engine", "lama"))
                retry_engine = self.quality_router.select_model(
                    "inpainting", current_engine, quality_score, self.provider_manifest
                )
                inpainted_image = self.inpainting_service.clean_background(
                    image,
                    boxes,
                    bubble_clip_boxes(local_bubbles),
                    source_polygons=bubble_source_polygons(local_bubbles),
                    protect_edges=True,
                    engine=retry_engine,
                    mask_dilation=max(1, int(getattr(config, "inpaint_mask_dilation", 2)) + 2),
                )
                quality_score = self.quality_router.evaluate_inpainting(image, inpainted_image, boxes)
                context.artifacts.setdefault("quality_replans", []).append({
                    "stage": "inpainting", "engine": retry_engine, "passed": quality_score.passed
                })
            context.artifacts.setdefault("quality_scores", {})["inpainting"] = quality_score
            if inpainted_image is None or getattr(inpainted_image, "shape", None) != getattr(image, "shape", None):
                raise RuntimeError("Inpainting did not produce a valid page image")

        context.artifacts["inpainted_image"] = inpainted_image
        context.artifacts["inpaint_result"] = inpainted_image
        return context


class PageLayoutStage:
    name = "layout"

    def run(self, context: PipelineContext) -> PipelineContext:
        context.artifacts["layout_result"] = context.artifacts["local_bubbles"]
        return context


class PageRenderingStage:
    name = "rendering"

    def __init__(
        self,
        *,
        encode_preview_jpeg_bytes: Any,
        encode_thumbnail_bytes: Any,
        refresh_page_status: Any,
        invalidate_page_caches: Any,
    ) -> None:
        self.encode_preview_jpeg_bytes = encode_preview_jpeg_bytes
        self.encode_thumbnail_bytes = encode_thumbnail_bytes
        self.refresh_page_status = refresh_page_status
        self.invalidate_page_caches = invalidate_page_caches

    def run(self, context: PipelineContext) -> PipelineContext:
        state = context.artifacts["state"]
        job = context.artifacts["job"]
        job_manager = context.artifacts["job_manager"]
        show_progress = context.artifacts["show_progress"]
        page_id = context.page_id
        inpainted_image = context.artifacts["inpainted_image"]
        local_bubbles = context.artifacts["local_bubbles"]
        bubble_counter = context.artifacts["bubble_counter"]
        start_revision = context.artifacts["start_revision"]

        if show_progress:
            job_manager.update(job, progress=80, message=msg_from_context("page_translation.rendering", context))
        job_manager.ensure_not_cancelled(job)
        inpainted_preview_bytes = self.encode_preview_jpeg_bytes(inpainted_image) if inpainted_image is not None else None
        job_manager.ensure_not_cancelled(job)

        with state.lock:
            _ensure_project_revision(state, start_revision)
            page_idx = _resolve_page_index(state, page_id)
            page = state.pages[page_idx]
            page.bubbles = local_bubbles
            page.bubble_counter = bubble_counter
            page.inpainted_image = inpainted_image
            self.refresh_page_status(page)
            self.invalidate_page_caches(page, thumbnails=True, responses=True)
            page._thumbnail_original_bytes = self.encode_thumbnail_bytes(page.cv_image)
            if inpainted_preview_bytes is not None:
                page._preview_inpainted_bytes = inpainted_preview_bytes
            state.touch()

        context.artifacts["render_result"] = page
        context.artifacts["result"] = {"translated_count": len(page.bubbles)}
        return context


def build_page_translation_runner(
    *,
    detection_service: Any,
    inpainting_service: Any,
    translation_service: Any,
    page_analysis_service: Any,
    bubble_analysis_service: Any,
    layout_planner_service: Any,
    ensure_page_image: Any,
    invalidate_page_caches: Any,
    encode_preview_jpeg_bytes: Any,
    encode_thumbnail_bytes: Any,
    refresh_page_status: Any,
    provider_manifests: dict[str, Any] | None = None,
) -> PipelineRunner:
    registry = StageRegistry()
    quality_router = AdaptiveQualityRouter()
    registry.register(
        PageDetectionStage(
            detection_service,
            ensure_page_image=ensure_page_image,
            quality_router=quality_router,
            provider_manifest=(provider_manifests or {}).get("detection"),
        )
    )
    registry.register(
        PageOcrStage(
            page_analysis_service=page_analysis_service,
            bubble_analysis_service=bubble_analysis_service,
            layout_planner_service=layout_planner_service,
            detection_service=detection_service,
            quality_router=quality_router,
            provider_manifest=(provider_manifests or {}).get("ocr"),
        )
    )
    registry.register(PageTranslationStage(translation_service))
    registry.register(PageInpaintingStage(
        inpainting_service,
        quality_router=quality_router,
        provider_manifest=(provider_manifests or {}).get("inpainting"),
    ))
    registry.register(PageLayoutStage())
    registry.register(
        PageRenderingStage(
            encode_preview_jpeg_bytes=encode_preview_jpeg_bytes,
            encode_thumbnail_bytes=encode_thumbnail_bytes,
            refresh_page_status=refresh_page_status,
            invalidate_page_caches=invalidate_page_caches,
        )
    )
    return PipelineRunner(registry)
