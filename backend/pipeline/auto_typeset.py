import concurrent.futures
import logging
from typing import List

import numpy as np
from fastapi import HTTPException

from app.models import TextBubble
from app.version import APP_NAME
from core.models.image import ImageData
from modules.utils.textblock import TextBlock
from pipeline.context import PipelineContext
from pipeline.plan import PipelinePlan
from pipeline.registry import StageRegistry
from pipeline.runner import PipelineResult, PipelineRunner
from services.image_encoding_service import encode_preview_jpeg_bytes, encode_thumbnail_bytes
from services.page_image_loader import ensure_page_image, invalidate_page_caches
from services.review_state_service import refresh_page_status
from services.bubble_analysis_service import BubbleAnalysisService
from services.layout_planner_service import LayoutPlannerService
from services.page_analysis_service import PageAnalysisService


logger = logging.getLogger(APP_NAME)

page_analysis_service = PageAnalysisService()
bubble_analysis_service = BubbleAnalysisService()
layout_planner_service = LayoutPlannerService()


def inpaint_boxes(bubbles, *, use_textbox_only: bool = True) -> list:
    """Boxes to inpaint per bubble.

    When INPAINT_USE_TEXTBOX_ONLY is on, clean only the detected text area
    (source_xyxy); otherwise clean the full speech-bubble box.
    """
    if use_textbox_only:
        return [b.source_xyxy() for b in bubbles]
    boxes = []
    for b in bubbles:
        box = b.box
        boxes.append([box.x(), box.y(), box.x() + box.width(), box.y() + box.height()])
    return boxes


def bubble_clip_boxes(bubbles) -> list:
    boxes = []
    for b in bubbles:
        box = b.box
        boxes.append([box.x(), box.y(), box.x() + box.width(), box.y() + box.height()])
    return boxes


def _rect_from_xyxy(xyxy):
    from PySide6.QtCore import QRectF

    x1, y1, x2, y2 = map(int, xyxy)
    return QRectF(x1, y1, x2 - x1, y2 - y1)


def _color_to_hex(color) -> str:
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        return color
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        try:
            r, g, b = [max(0, min(255, int(v))) for v in color[:3]]
            return f"#{r:02x}{g:02x}{b:02x}"
        except (TypeError, ValueError):
            pass
    return "#000000"


def _contains_cjk(text: str) -> bool:
    return any(
        "\u3040" <= ch <= "\u30ff"
        or "\u3400" <= ch <= "\u9fff"
        or "\uac00" <= ch <= "\ud7af"
        for ch in text
    )


def _join_merged_text(parts: list[str]) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return ""
    separator = "\n" if any(_contains_cjk(part) for part in cleaned) else " "
    return separator.join(cleaned)


def _insets_to_dict(insets) -> dict[str, float]:
    return {
        "top": float(getattr(insets, "top", 0.0)),
        "right": float(getattr(insets, "right", 0.0)),
        "bottom": float(getattr(insets, "bottom", 0.0)),
        "left": float(getattr(insets, "left", 0.0)),
    }


def _bubbles_from_analysis(
    image: np.ndarray,
    blocks: list,
    source_lang: str,
    target_lang: str,
    *,
    config,
    page_analysis_service,
    bubble_analysis_service,
    layout_planner_service,
) -> list:
    """Create TextBubbles using the full analysis pipeline."""
    from services.layout_planner_service import BubbleLayoutInput

    page_result = page_analysis_service.analyze(
        image,
        source_lang=source_lang,
        text_blocks=blocks,
    )

    bubble_result = bubble_analysis_service.analyze(
        image,
        blocks,
        source_lang=source_lang,
    )

    if not bubble_result.bubbles:
        return []

    bubbles = []
    for idx, bd in enumerate(bubble_result.bubbles):
        if config.bubbles_only and bd.text_class == "text_free":
            continue
        if not bd.text or not bd.text.strip():
            continue

        text_rect = _rect_from_xyxy(bd.text_box)
        bubble_rect = _rect_from_xyxy(bd.bubble_box)

        layout_inp = BubbleLayoutInput(
            bubble_box=bubble_rect,
            layout_box=_rect_from_xyxy(bd.layout_box),
            text=bd.text,
            text_class=bd.text_class,
            page_reading_order=page_result.reading_order.direction,
            page_writing_mode=page_result.writing_mode,
        )
        layout_plan = layout_planner_service.plan(layout_inp)

        tb = TextBubble(
            id=idx + 1,
            box=bubble_rect,
            text=bd.text,
            translated="",
            text_box=text_rect,
            layout_box=_rect_from_xyxy(bd.layout_box),
            text_class=bd.text_class,
        )
        tb.font_family = ""
        tb.font_size = 0
        tb.color = _color_to_hex(bd.font_color)
        tb.alignment = layout_plan.alignment
        tb.writing_mode = getattr(layout_plan, "writing_mode", "horizontal")
        tb.text_direction = getattr(layout_plan, "text_direction", "ltr")
        tb.justification = getattr(layout_plan, "justification", "none")
        tb.layout_padding = _insets_to_dict(getattr(layout_plan, "padding", None))
        tb.layout_margin = _insets_to_dict(getattr(layout_plan, "margin", None))
        tb.layout_confidence = float(getattr(layout_plan, "confidence", 0.0) or 0.0)
        tb.layout_reasoning = getattr(layout_plan, "reasoning", "")

        bubbles.append(tb)

    return bubbles


def _merge_overlapping_bubbles(bubbles: list[TextBubble], iou_threshold: float = 0.25) -> list[TextBubble]:
    """Merge bubbles whose bounding boxes overlap significantly."""
    if len(bubbles) < 2:
        return bubbles

    def _iou(a: TextBubble, b: TextBubble) -> float:
        ax1, ay1 = a.box.x(), a.box.y()
        ax2, ay2 = ax1 + a.box.width(), ay1 + a.box.height()
        bx1, by1 = b.box.x(), b.box.y()
        bx2, by2 = bx1 + b.box.width(), by1 + b.box.height()
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        area_a = a.box.width() * a.box.height()
        area_b = b.box.width() * b.box.height()
        union = area_a + area_b - inter
        if union <= 0:
            return 0.0
        return inter / union

    merged = True
    current = list(bubbles)
    while merged:
        merged = False
        i = 0
        while i < len(current):
            j = i + 1
            while j < len(current):
                if _iou(current[i], current[j]) >= iou_threshold:
                    ai = current[i]
                    aj = current[j]
                    ax1 = min(ai.box.x(), aj.box.x())
                    ay1 = min(ai.box.y(), aj.box.y())
                    ax2 = max(ai.box.x() + ai.box.width(), aj.box.x() + aj.box.width())
                    ay2 = max(ai.box.y() + ai.box.height(), aj.box.y() + aj.box.height())
                    from PySide6.QtCore import QRectF
                    ai.box = QRectF(ax1, ay1, ax2 - ax1, ay2 - ay1)

                    ait = ai.text_box
                    ajt = aj.text_box
                    if ait is not None and ajt is not None:
                        tx1 = min(ait.x(), ajt.x())
                        ty1 = min(ait.y(), ajt.y())
                        tx2 = max(ait.x() + ait.width(), ajt.x() + ajt.width())
                        ty2 = max(ait.y() + ait.height(), ajt.y() + ajt.height())
                        ai.text_box = QRectF(tx1, ty1, tx2 - tx1, ty2 - ty1)
                    elif ajt is not None:
                        ai.text_box = QRectF(ajt)

                    ail = ai.layout_box
                    ajl = aj.layout_box
                    if ail is not None and ajl is not None:
                        lx1 = min(ail.x(), ajl.x())
                        ly1 = min(ail.y(), ajl.y())
                        lx2 = max(ail.x() + ail.width(), ajl.x() + ajl.width())
                        ly2 = max(ail.y() + ail.height(), ajl.y() + ajl.height())
                        ai.layout_box = QRectF(lx1, ly1, lx2 - lx1, ly2 - ly1)
                    elif ajl is not None:
                        ai.layout_box = QRectF(ajl)

                    merged_text = _join_merged_text([ai.text, aj.text])
                    if merged_text:
                        ai.text = merged_text
                    merged_translation = _join_merged_text([ai.translated, aj.translated])
                    if merged_translation:
                        ai.translated = merged_translation
                    current.pop(j)
                    merged = True
                    continue
                j += 1
            i += 1
    return current


class _AutoTypesetStage:
    def __init__(self, name: str, method_name: str) -> None:
        self.name = name
        self.method_name = method_name

    def run(self, context: PipelineContext) -> PipelineContext:
        pipeline = context.artifacts["pipeline"]
        return getattr(pipeline, self.method_name)(context)


class AutoTypesetPipeline:
    _PAGE_PLAN = PipelinePlan(
        stages=[
            "load_page",
            "detect_analyze",
            "inpaint_translate",
            "commit_page",
        ]
    )

    def __init__(
        self,
        *,
        state,
        config,
        job_manager,
        detection_service,
        inpainting_service,
        translation_service,
        page_analysis_service=None,
        bubble_analysis_service=None,
        layout_planner_service=None,
    ) -> None:
        self.state = state
        self.config = config
        self.job_manager = job_manager
        self.detection_service = detection_service
        self.inpainting_service = inpainting_service
        self.translation_service = translation_service
        self.page_analysis_service = page_analysis_service or PageAnalysisService()
        self.bubble_analysis_service = bubble_analysis_service or BubbleAnalysisService()
        self.layout_planner_service = layout_planner_service or LayoutPlannerService()
        self.last_result: PipelineResult | None = None

    def _build_page_runner(self) -> PipelineRunner:
        registry = StageRegistry()
        registry.register(_AutoTypesetStage("load_page", "_stage_load_page"))
        registry.register(_AutoTypesetStage("detect_analyze", "_stage_detect_analyze"))
        registry.register(_AutoTypesetStage("inpaint_translate", "_stage_inpaint_translate"))
        registry.register(_AutoTypesetStage("commit_page", "_stage_commit_page"))
        return PipelineRunner(registry)

    def _resolve_page_index(self, page_id: str) -> int:
        if page_id.isdigit():
            idx = int(page_id)
            if 0 <= idx < len(self.state.pages):
                return idx
            raise HTTPException(status_code=404, detail="Page not found")
        for idx, page in enumerate(self.state.pages):
            if page.page_id == page_id:
                return idx
        raise HTTPException(status_code=404, detail="Page not found")

    def _ensure_project_revision(self, start_revision: int) -> None:
        if self.state.revision != start_revision:
            raise RuntimeError("Project changed while the operation was running. Please retry.")

    def run_page(self, job: dict, page_id: str, *, show_progress: bool = True) -> dict[str, int]:
        context = PipelineContext(
            page_id=page_id,
            page=None,
            image=ImageData(array=None),
            settings=self.config,
            artifacts={
                "job": job,
                "show_progress": show_progress,
                "pipeline": self,
            },
        )
        result = self._build_page_runner().run(context, self._PAGE_PLAN)
        self.last_result = result
        if not result.succeeded:
            message = result.issues[0].message if result.issues else "Auto typeset pipeline failed"
            raise RuntimeError(message)
        return result.context.artifacts["result"]

    def run_batch(self, job: dict, page_ids: List[str]) -> dict:
        total = len(page_ids)
        completed = 0
        completed_page_indices = []

        for page_id in page_ids:
            page_idx = None
            try:
                with self.state.lock:
                    page_idx = self._resolve_page_index(page_id)
                self.job_manager.update(
                    job,
                    progress=int((completed / total) * 100),
                    message=f"Translating page {completed + 1}/{total}...",
                )
                job["result"] = {"completed_pages": list(completed_page_indices), "total_pages": total}
                self.run_page(job, page_id, show_progress=False)
            except HTTPException:
                logger.warning("Batch: page_id %s not found (may have been deleted)", page_id)
            except RuntimeError as e:
                if "cancelled" in str(e).lower():
                    raise
                logger.warning("Batch: page_id %s failed: %s", page_id, e)
                completed += 1
                continue

            completed += 1
            if page_idx is not None:
                completed_page_indices.append(page_idx)
                self.job_manager.ensure_not_cancelled(job)

        self.job_manager.update(job, progress=100, message="Batch translation complete")
        return {"translated_pages": completed, "total_pages": total, "completed_pages": completed_page_indices}

    def _stage_load_page(self, context: PipelineContext) -> PipelineContext:
        page_id = context.page_id
        with self.state.lock:
            page_idx = self._resolve_page_index(page_id)
            page = self.state.pages[page_idx]
            ensure_page_image(page)
            start_revision = self.state.revision
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
            }
        )
        return context

    def _stage_detect_analyze(self, context: PipelineContext) -> PipelineContext:
        job = context.artifacts["job"]
        show_progress = context.artifacts["show_progress"]
        image = context.artifacts["image"]
        local_bubbles = context.artifacts["local_bubbles"]
        bubble_counter = context.artifacts["bubble_counter"]

        self.job_manager.ensure_not_cancelled(job)
        if not local_bubbles:
            if show_progress:
                self.job_manager.update(job, progress=15, message="Detecting and reading text")
            blocks = self.detection_service.detect_and_ocr(image, lang=self.config.source_language)
            self.job_manager.ensure_not_cancelled(job)

            if show_progress:
                self.job_manager.update(job, progress=30, message="Analyzing page layout")
            local_bubbles = _bubbles_from_analysis(
                image,
                blocks,
                self.config.source_language,
                self.config.target_language,
                config=self.config,
                page_analysis_service=self.page_analysis_service,
                bubble_analysis_service=self.bubble_analysis_service,
                layout_planner_service=self.layout_planner_service,
            )
            self.job_manager.ensure_not_cancelled(job)

            local_bubbles = _merge_overlapping_bubbles(local_bubbles)
            for idx, bubble in enumerate(local_bubbles, 1):
                bubble.id = idx
            bubble_counter = len(local_bubbles)
            self.job_manager.ensure_not_cancelled(job)

        context.artifacts["local_bubbles"] = local_bubbles
        context.artifacts["bubble_counter"] = bubble_counter
        return context

    def _stage_inpaint_translate(self, context: PipelineContext) -> PipelineContext:
        job = context.artifacts["job"]
        show_progress = context.artifacts["show_progress"]
        image = context.artifacts["image"]
        inpainted_image = context.artifacts["inpainted_image"]
        local_bubbles = context.artifacts["local_bubbles"]
        untranslated = [b for b in local_bubbles if not b.translated]
        temp_blocks = []

        def task_inpaint():
            nonlocal inpainted_image
            if inpainted_image is None:
                boxes = inpaint_boxes(local_bubbles, use_textbox_only=self.config.inpaint_use_textbox_only)
                bubble_boxes = bubble_clip_boxes(local_bubbles)
                inpainted_image = self.inpainting_service.clean_background(image, boxes, bubble_boxes, protect_edges=True)

        def task_translate():
            nonlocal temp_blocks
            if untranslated:
                temp_blocks = [
                    TextBlock(text_bbox=np.array(b.source_xyxy()).astype(np.int32), text=b.text)
                    for b in untranslated
                ]
                self.translation_service.translate_blocks(temp_blocks, self.config.source_language, self.config.target_language, image)

        if show_progress:
            self.job_manager.update(job, progress=45, message="Translating text and cleaning backgrounds in parallel")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(task_inpaint),
                executor.submit(task_translate),
            ]
            for future in concurrent.futures.as_completed(futures):
                self.job_manager.ensure_not_cancelled(job)
                future.result()

        if untranslated and temp_blocks:
            for bubble, text_block in zip(untranslated, temp_blocks):
                bubble.translated = text_block.translation

        context.artifacts["inpainted_image"] = inpainted_image
        context.artifacts["temp_blocks"] = temp_blocks
        return context

    def _stage_commit_page(self, context: PipelineContext) -> PipelineContext:
        job = context.artifacts["job"]
        page_id = context.page_id
        image = context.artifacts["image"]
        inpainted_image = context.artifacts["inpainted_image"]
        local_bubbles = context.artifacts["local_bubbles"]
        bubble_counter = context.artifacts["bubble_counter"]
        start_revision = context.artifacts["start_revision"]

        self.job_manager.ensure_not_cancelled(job)
        inpainted_preview_bytes = encode_preview_jpeg_bytes(inpainted_image) if inpainted_image is not None else None
        self.job_manager.ensure_not_cancelled(job)

        with self.state.lock:
            self._ensure_project_revision(start_revision)
            self.job_manager.ensure_not_cancelled(job)
            page_idx = self._resolve_page_index(page_id)
            page = self.state.pages[page_idx]
            page.bubbles = local_bubbles
            page.bubble_counter = bubble_counter
            page.inpainted_image = inpainted_image
            refresh_page_status(page)
            invalidate_page_caches(page, thumbnails=True, responses=True)
            page._thumbnail_original_bytes = encode_thumbnail_bytes(page.cv_image)
            if inpainted_preview_bytes is not None:
                page._preview_inpainted_bytes = inpainted_preview_bytes
            self.state.touch()
        context.artifacts["result"] = {"translated_count": len(page.bubbles)}
        return context
