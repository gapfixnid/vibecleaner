from __future__ import annotations

import logging
import math
from types import SimpleNamespace
from typing import Any

from ..core.errors import PageNotFoundError
from ..core.models.image import ImageData
from ..core.models import (
    BubbleProblemCode,
    reconcile_bubble_problems,
)
from ..core.text.graphemes import grapheme_count
from ..infrastructure.job_messages import msg_from_context
from ..engines.rendering.bubble_layout import bubble_layout_cache_key, compute_bubble_layout
from ..engines.ocr.retry import OcrSnapshot, choose_ocr_retry
from .page_analysis import (
    bubbles_from_analysis,
    merge_overlapping_bubbles,
    bubble_clip_boxes,
    bubble_source_polygons,
    inpaint_boxes,
    recover_missing_source_polygons,
)
from .context import PipelineContext, PipelineSnapshot, StageOutput
from .registry import StageRegistry
from .runner import PipelineRunner
from .quality import AdaptiveQualityRouter
from .validation.results import PipelineValidationError, ValidationIssue

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


def _quality_rank(
    score: Any,
) -> tuple[int, float, float, float, float, float]:
    signals = dict(getattr(score, "signals", {}) or {})
    return (
        1 if bool(getattr(score, "passed", False)) else 0,
        -float(signals.get("invalid_box_ratio", 0.0)),
        -float(signals.get("unmatched_ratio", 0.0)),
        -float(signals.get("ambiguous_match_ratio", 0.0)),
        float(
            signals.get(
                "mean_confidence",
                getattr(score, "score", 0.0),
            )
        ),
        float(signals.get("matched", 0.0)),
    )


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


def _ensure_page_guard(state: Any, context: PipelineContext) -> Any:
    if state.project_generation != context.artifacts["project_generation"]:
        raise PipelineValidationError([ValidationIssue(
            code="PROJECT_REVISION_CONFLICT", severity="error",
            message="Project was replaced while the operation was running. Please retry.",
            stage="commit", retryable=True, details={"page_id": context.page_id},
        )])
    page_idx = _resolve_page_index(state, context.page_id)
    page = state.pages[page_idx]
    if page is not context.artifacts["snapshot_page"]:
        raise PipelineValidationError([ValidationIssue(
            code="PAGE_REVISION_CONFLICT", severity="error",
            message="Page was replaced while the operation was running. Please retry.",
            stage="commit", retryable=True, details={"page_id": context.page_id},
        )])
    if page.visual_revision != context.artifacts["visual_revision"]:
        raise PipelineValidationError([ValidationIssue(
            code="PAGE_REVISION_CONFLICT", severity="error",
            message="Page changed while the operation was running. Please retry.",
            stage="commit", retryable=True,
            details={"page_id": context.page_id,
                     "expected_visual_revision": context.artifacts["visual_revision"],
                     "actual_visual_revision": page.visual_revision},
        )])
    return page


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
                "project_generation": state.project_generation,
                "visual_revision": page.visual_revision,
                "snapshot_page": page,
                "image_visual_revision": page.image_visual_revision,
                "image": image,
                "inpainted_image": inpainted_image,
                "local_bubbles": local_bubbles,
                "bubble_counter": bubble_counter,
                "blocks": [],
            }
        )
        context.artifacts["ocr_snapshot"] = PipelineSnapshot(
            page_id=context.page_id,
            project_generation=state.project_generation,
            visual_revision=page.visual_revision,
            image_visual_revision=page.image_visual_revision,
            bubbles=tuple(bubble.clone() for bubble in local_bubbles),
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
                    retry_blocks = self.detection_service.detect_only(
                        image, model_name=selected_model
                    )
                    retry_score = self.quality_router.evaluate_detection(
                        retry_blocks
                    )
                    retry_selected = (
                        _quality_rank(retry_score)
                        > _quality_rank(detection_score)
                    )
                    if retry_selected:
                        blocks = retry_blocks
                        detection_score = retry_score
                    context.artifacts.setdefault("quality_replans", []).append(
                        {
                            "stage": "detection",
                            "model": selected_model,
                            "selected": "retry"
                            if retry_selected
                            else "initial",
                        }
                    )
                context.artifacts["blocks"] = blocks
                context.artifacts["ocr_pending"] = True
                context.artifacts.setdefault("quality_scores", {})["detection"] = (
                    detection_score
                )
                context.artifacts.setdefault(
                    "quality_aggregates", {}
                )["detection_association"] = dict(
                    detection_score.signals
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
                    retry_blocks = [
                        block.deep_copy() for block in suspicious_blocks
                    ]
                    retry_padding = max(1, int(getattr(config, "ocr_padding", 8)) * 2)
                    retry_scale = max(1.0, float(getattr(config, "ocr_crop_scale", 1.5)) * 1.25)
                    retry_engine = config.ocr_engine
                    self.detection_service.ocr_only(
                        image,
                        retry_blocks,
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
                    rejected_blocks = 0
                    for block, retry_block in zip(
                        suspicious_blocks, retry_blocks
                    ):
                        decision = choose_ocr_retry(
                            OcrSnapshot(
                                str(getattr(block, "text", "") or ""),
                                getattr(block, "ocr_confidence", None),
                            ),
                            OcrSnapshot(
                                str(
                                    getattr(
                                        retry_block, "text", ""
                                    )
                                    or ""
                                ),
                                getattr(
                                    retry_block,
                                    "ocr_confidence",
                                    None,
                                ),
                            ),
                            config.source_language,
                        )
                        if decision.accepted:
                            block.text = decision.selected.text
                            block.ocr_confidence = (
                                decision.selected.confidence
                            )
                            block.problem_codes.discard(
                                "OCR_UNCERTAIN"
                            )
                            recovered_blocks += 1
                        else:
                            if decision.uncertain:
                                block.problem_codes.add(
                                    "OCR_UNCERTAIN"
                                )
                            else:
                                block.problem_codes.discard(
                                    "OCR_UNCERTAIN"
                                )
                            rejected_blocks += 1
                    ocr_score = self.quality_router.evaluate_ocr(
                        context.artifacts["blocks"], config.source_language
                    )
                    context.artifacts.setdefault("quality_replans", []).append({
                        "stage": "ocr", "model": retry_engine,
                        "profile": "suspicious_text_recovery", "recovered_blocks": recovered_blocks,
                        "candidate_blocks": len(suspicious_blocks),
                        "rejected_blocks": rejected_blocks,
                        "passed": ocr_score.passed,
                    })
                if not ocr_score.passed:
                    retry_engine = self.quality_router.select_model(
                        "ocr", config.ocr_engine, ocr_score, self.provider_manifest
                    )
                    retry_padding = max(1, int(getattr(config, "ocr_padding", 8)) * 2)
                    retry_scale = max(1.0, float(getattr(config, "ocr_crop_scale", 1.5)) * 1.25)
                    original_blocks = context.artifacts["blocks"]
                    retry_blocks = [
                        block.deep_copy() for block in original_blocks
                    ]
                    self.detection_service.ocr_only(
                        image,
                        retry_blocks,
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
                    accepted_blocks = 0
                    for block, retry_block in zip(
                        original_blocks, retry_blocks
                    ):
                        decision = choose_ocr_retry(
                            OcrSnapshot(
                                str(getattr(block, "text", "") or ""),
                                getattr(block, "ocr_confidence", None),
                            ),
                            OcrSnapshot(
                                str(
                                    getattr(
                                        retry_block, "text", ""
                                    )
                                    or ""
                                ),
                                getattr(
                                    retry_block,
                                    "ocr_confidence",
                                    None,
                                ),
                            ),
                            config.source_language,
                        )
                        if decision.accepted:
                            block.text = decision.selected.text
                            block.ocr_confidence = (
                                decision.selected.confidence
                            )
                            block.problem_codes.discard(
                                "OCR_UNCERTAIN"
                            )
                            accepted_blocks += 1
                        elif decision.uncertain:
                            block.problem_codes.add("OCR_UNCERTAIN")
                    ocr_score = self.quality_router.evaluate_ocr(
                        original_blocks, config.source_language
                    )
                    context.artifacts.setdefault("quality_replans", []).append({
                        "stage": "ocr", "model": retry_engine,
                        "profile": "enhanced_preprocessing",
                        "accepted_blocks": accepted_blocks,
                        "passed": ocr_score.passed,
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
        context.artifacts["ocr_snapshot"] = PipelineSnapshot(
            page_id=context.page_id,
            project_generation=context.artifacts["project_generation"],
            visual_revision=context.artifacts["visual_revision"],
            image_visual_revision=context.artifacts["image_visual_revision"],
            bubbles=tuple(bubble.clone() for bubble in local_bubbles),
        )
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
        ocr_replans = [
            item
            for item in context.artifacts.get(
                "quality_replans", []
            )
            if item.get("stage") == "ocr"
        ]
        context.artifacts.setdefault(
            "quality_aggregates", {}
        )["ocr_retry"] = {
            "attempted": sum(
                int(item.get("candidate_blocks", 0))
                for item in ocr_replans
            ),
            "accepted": sum(
                int(
                    item.get(
                        "recovered_blocks",
                        item.get("accepted_blocks", 0),
                    )
                )
                for item in ocr_replans
            ),
            "rejected": sum(
                int(item.get("rejected_blocks", 0))
                for item in ocr_replans
            ),
        }
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
        snapshot = context.artifacts["ocr_snapshot"]
        local_bubbles = [bubble.clone() for bubble in snapshot.bubbles]
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
        context.artifacts["translation_result"] = tuple(local_bubbles)
        context.artifacts["translation_output"] = StageOutput(
            stage=self.name,
            values={"bubbles": tuple(local_bubbles), "temp_blocks": tuple(temp_blocks)},
        )
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
        snapshot = context.artifacts["ocr_snapshot"]
        local_bubbles = [bubble.clone() for bubble in snapshot.bubbles]

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
                current_engine = str(getattr(config, "inpaint_engine", "aot"))
                retry_engine = self.quality_router.select_model(
                    "inpainting", current_engine, quality_score, self.provider_manifest
                )
                if retry_engine != current_engine:
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
        context.artifacts["inpainting_output"] = StageOutput(
            stage=self.name, values={"image": inpainted_image}
        )
        return context


class PageLayoutStage:
    name = "layout"

    def __init__(self, render_service: Any, text_layer_service: Any | None = None) -> None:
        self.render_service = render_service
        self.text_layer_service = text_layer_service

    def run(self, context: PipelineContext) -> PipelineContext:
        job = context.artifacts["job"]
        job_manager = context.artifacts["job_manager"]
        image = context.artifacts["image"]
        translation_output = context.artifacts.get("translation_output")
        source_bubbles = (
            translation_output.values["bubbles"]
            if isinstance(translation_output, StageOutput)
            else context.artifacts.get("translation_result", context.artifacts["local_bubbles"])
        )
        local_bubbles = [bubble.clone() for bubble in source_bubbles]
        layout_cache = {}
        text_layer_refs = {}
        render_statuses = {}
        layout_diagnostics: list[dict[str, Any]] = []
        translation_ratios: list[float] = []
        expanded_count = 0
        for bubble in local_bubbles:
            job_manager.ensure_not_cancelled(job)
            layout = None
            if self.text_layer_service is not None and (bubble.translated or "").strip():
                try:
                    tile = self.text_layer_service.create_tile(
                        context.page_id,
                        bubble,
                        image,
                        image_revision=context.artifacts.get("image_visual_revision", 0),
                    )
                    layout = tile.layout
                    diagnostics = dict(
                        tile.layout.get("diagnostics", {}) or {}
                    )
                    if diagnostics:
                        layout_diagnostics.append(diagnostics)
                    layout_cache[bubble_layout_cache_key(bubble)] = layout
                    text_layer_refs[bubble.id] = {
                        "layout_fingerprint": tile.layout_fingerprint,
                        "render_fingerprint": tile.render_fingerprint,
                        "cache_key": tile.cache_key,
                        "pixel_digest": tile.pixel_digest,
                        "crop_x": tile.crop_x,
                        "crop_y": tile.crop_y,
                        "width": tile.width,
                        "height": tile.height,
                    }
                    render_statuses[bubble.id] = {"status": "ready", "error_code": None}
                except Exception as exc:
                    logger.warning("Translation tile fallback. bubble_id=%s error=%s", bubble.id, exc)
                    render_statuses[bubble.id] = {"status": "fallback", "error_code": str(exc)}
            if layout is None:
                layout = compute_bubble_layout(
                    bubble, image, self.render_service
                )
                layout_cache[bubble_layout_cache_key(bubble)] = layout

            derived = {
                BubbleProblemCode(code)
                for code in bubble._derived_problem_codes
                if code in BubbleProblemCode._value2member_map_
            }
            overflow = bool(
                layout.get("overflow")
                or layout.get("reached_min_font")
            )
            if overflow:
                derived.add(BubbleProblemCode.TEXT_OVERFLOW)
            source_length = grapheme_count(bubble.text)
            translated_length = grapheme_count(bubble.translated)
            expanded = (
                translated_length
                > max(24, math.ceil(source_length * 1.8))
                and overflow
            )
            if expanded:
                derived.add(
                    BubbleProblemCode.TRANSLATION_EXPANDED
                )
                expanded_count += 1
            if source_length:
                translation_ratios.append(
                    translated_length / source_length
                )
            bubble.problems = reconcile_bubble_problems(
                bubble.problems,
                derived=derived,
            )
        selected_passes: dict[str, int] = {}
        for diagnostics in layout_diagnostics:
            selected = str(
                diagnostics.get("selected_pass", "fallback")
            )
            selected_passes[selected] = (
                selected_passes.get(selected, 0) + 1
            )
        sorted_ratios = sorted(translation_ratios)

        def percentile(values: list[float], ratio: float) -> float:
            if not values:
                return 0.0
            index = min(
                len(values) - 1,
                int(round((len(values) - 1) * ratio)),
            )
            return round(values[index], 4)

        context.artifacts.setdefault("quality_aggregates", {}).update(
            {
                "layout_selection": {
                    **selected_passes,
                    "mean_rasterized_candidates": round(
                        sum(
                            float(
                                item.get(
                                    "rasterized_candidate_count", 0
                                )
                            )
                            for item in layout_diagnostics
                        )
                        / max(1, len(layout_diagnostics)),
                        4,
                    ),
                },
                "translation_length": {
                    "count": len(translation_ratios),
                    "p50_ratio": percentile(
                        sorted_ratios, 0.50
                    ),
                    "p90_ratio": percentile(
                        sorted_ratios, 0.90
                    ),
                    "expanded_count": expanded_count,
                },
            }
        )
        context.artifacts["bubble_layout_cache"] = layout_cache
        context.artifacts["text_layer_refs"] = text_layer_refs
        context.artifacts["bubble_render_status"] = render_statuses
        context.artifacts["layout_result"] = tuple(local_bubbles)
        context.artifacts["layout_output"] = StageOutput(
            stage=self.name,
            values={
                "bubbles": tuple(local_bubbles),
                "bubble_layout_cache": layout_cache,
                "text_layer_refs": text_layer_refs,
                "bubble_render_status": render_statuses,
            },
        )
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
        local_bubbles = list(context.artifacts["layout_result"])
        bubble_counter = context.artifacts["bubble_counter"]
        bubble_layout_cache = context.artifacts.get("bubble_layout_cache", {})

        if show_progress:
            job_manager.update(job, progress=80, message=msg_from_context("page_translation.rendering", context))
        job_manager.ensure_not_cancelled(job)
        inpainted_preview_bytes = self.encode_preview_jpeg_bytes(inpainted_image) if inpainted_image is not None else None
        thumbnail_original_bytes = self.encode_thumbnail_bytes(context.artifacts["image"])
        job_manager.ensure_not_cancelled(job)

        with state.lock:
            job_manager.ensure_not_cancelled(job)
            page = _ensure_page_guard(state, context)
            page.bubbles = local_bubbles
            page.bubble_counter = bubble_counter
            page.inpainted_image = inpainted_image
            self.refresh_page_status(page)
            self.invalidate_page_caches(page, thumbnails=True, responses=True)
            page._bubble_layout_cache = dict(bubble_layout_cache)
            page.text_layer_refs = dict(context.artifacts.get("text_layer_refs", {}))
            page.bubble_render_status = dict(context.artifacts.get("bubble_render_status", {}))
            page._thumbnail_original_bytes = thumbnail_original_bytes
            if inpainted_preview_bytes is not None:
                page._preview_inpainted_bytes = inpainted_preview_bytes
            page.visual_revision += 1
            state.touch()

        context.artifacts["render_result"] = page
        translated_count = sum(
            bool((bubble.translated or "").strip())
            for bubble in page.bubbles
        )
        context.artifacts["result"] = {"translated_count": translated_count}
        return context


def build_page_translation_runner(
    *,
    detection_service: Any,
    inpainting_service: Any,
    translation_service: Any,
    page_analysis_service: Any,
    bubble_analysis_service: Any,
    layout_planner_service: Any,
    render_service: Any,
    text_layer_service: Any | None = None,
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
    registry.register(PageLayoutStage(render_service, text_layer_service))
    registry.register(
        PageRenderingStage(
            encode_preview_jpeg_bytes=encode_preview_jpeg_bytes,
            encode_thumbnail_bytes=encode_thumbnail_bytes,
            refresh_page_status=refresh_page_status,
            invalidate_page_caches=invalidate_page_caches,
        )
    )
    return PipelineRunner(registry)
