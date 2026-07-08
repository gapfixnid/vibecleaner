from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException

from core.models.image import ImageData
from pipeline.page_analysis import (
    bubbles_from_analysis,
    merge_overlapping_bubbles,
    bubble_clip_boxes,
    inpaint_boxes,
)
from pipeline.context import PipelineContext
from pipeline.registry import StageRegistry
from pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)


def _resolve_page_index(state: Any, page_id: str) -> int:
    if page_id.isdigit():
        idx = int(page_id)
        if 0 <= idx < len(state.pages):
            return idx
        raise HTTPException(status_code=404, detail="Page not found")
    for idx, page in enumerate(state.pages):
        if page.page_id == page_id:
            return idx
    raise HTTPException(status_code=404, detail="Page not found")


def _ensure_project_revision(state: Any, start_revision: int) -> None:
    if state.revision != start_revision:
        raise RuntimeError("Project changed while the operation was running. Please retry.")


class PageDetectionStage:
    name = "detection"

    def __init__(self, detection_service: Any, *, ensure_page_image: Any) -> None:
        self.detection_service = detection_service
        self.ensure_page_image = ensure_page_image

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
            local_bubbles = [bubble.without_item() for bubble in page.bubbles]
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
                job_manager.update(job, progress=15, message="Detecting and reading text")
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
    ) -> None:
        self.page_analysis_service = page_analysis_service
        self.bubble_analysis_service = bubble_analysis_service
        self.layout_planner_service = layout_planner_service

    def run(self, context: PipelineContext) -> PipelineContext:
        job = context.artifacts["job"]
        job_manager = context.artifacts["job_manager"]
        show_progress = context.artifacts["show_progress"]
        config = context.artifacts["config"]
        image = context.artifacts["image"]
        local_bubbles = context.artifacts["local_bubbles"]

        if not local_bubbles:
            if show_progress:
                job_manager.update(job, progress=30, message="Analyzing page layout")
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
        return context


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
                job_manager.update(job, progress=45, message="Translating text")
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

    def __init__(self, inpainting_service: Any) -> None:
        self.inpainting_service = inpainting_service

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
                job_manager.update(job, progress=60, message="Cleaning backgrounds")
            boxes = inpaint_boxes(local_bubbles, use_textbox_only=config.inpaint_use_textbox_only)
            inpainted_image = self.inpainting_service.clean_background(
                image,
                boxes,
                bubble_clip_boxes(local_bubbles),
                protect_edges=True,
            )
            job_manager.ensure_not_cancelled(job)

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
        page_id = context.page_id
        inpainted_image = context.artifacts["inpainted_image"]
        local_bubbles = context.artifacts["local_bubbles"]
        bubble_counter = context.artifacts["bubble_counter"]
        start_revision = context.artifacts["start_revision"]

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
) -> PipelineRunner:
    registry = StageRegistry()
    registry.register(PageDetectionStage(detection_service, ensure_page_image=ensure_page_image))
    registry.register(
        PageOcrStage(
            page_analysis_service=page_analysis_service,
            bubble_analysis_service=bubble_analysis_service,
            layout_planner_service=layout_planner_service,
        )
    )
    registry.register(PageTranslationStage(translation_service))
    registry.register(PageInpaintingStage(inpainting_service))
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
