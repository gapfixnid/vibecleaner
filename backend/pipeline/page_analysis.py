from __future__ import annotations

from typing import Any

import numpy as np

from app.models import TextBubble
from services.bubble_analysis_service import BubbleAnalysisService
from services.layout_planner_service import LayoutPlannerService
from services.page_analysis_service import PageAnalysisService

page_analysis_service = PageAnalysisService()
bubble_analysis_service = BubbleAnalysisService()
layout_planner_service = LayoutPlannerService()


def inpaint_boxes(bubbles, *, use_textbox_only: bool = True) -> list:
    if use_textbox_only:
        return [bubble.source_xyxy() for bubble in bubbles]
    boxes = []
    for bubble in bubbles:
        box = bubble.box
        boxes.append([box.x(), box.y(), box.x() + box.width(), box.y() + box.height()])
    return boxes


def bubble_clip_boxes(bubbles) -> list:
    boxes = []
    for bubble in bubbles:
        box = bubble.box
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
            r, g, b = [max(0, min(255, int(value))) for value in color[:3]]
            return f"#{r:02x}{g:02x}{b:02x}"
        except (TypeError, ValueError):
            pass
    return "#000000"


def _contains_cjk(text: str) -> bool:
    return any(
        "\u3040" <= char <= "\u30ff"
        or "\u3400" <= char <= "\u9fff"
        or "\uac00" <= char <= "\ud7af"
        for char in text
    )


def _join_merged_text(parts: list[str]) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return ""
    separator = "\n" if any(_contains_cjk(part) for part in cleaned) else " "
    return separator.join(cleaned)


def _insets_to_dict(insets: Any) -> dict[str, float]:
    return {
        "top": float(getattr(insets, "top", 0.0)),
        "right": float(getattr(insets, "right", 0.0)),
        "bottom": float(getattr(insets, "bottom", 0.0)),
        "left": float(getattr(insets, "left", 0.0)),
    }


def bubbles_from_analysis(
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
    for index, bubble_data in enumerate(bubble_result.bubbles):
        if config.bubbles_only and bubble_data.text_class == "text_free":
            continue
        if not bubble_data.text or not bubble_data.text.strip():
            continue

        text_rect = _rect_from_xyxy(bubble_data.text_box)
        bubble_rect = _rect_from_xyxy(bubble_data.bubble_box)
        layout_box = _rect_from_xyxy(bubble_data.layout_box)
        layout_input = BubbleLayoutInput(
            bubble_box=bubble_rect,
            layout_box=layout_box,
            text=bubble_data.text,
            text_class=bubble_data.text_class,
            page_reading_order=page_result.reading_order.direction,
            page_writing_mode=page_result.writing_mode,
        )
        layout_plan = layout_planner_service.plan(layout_input)
        text_bubble = TextBubble(
            id=index + 1,
            box=bubble_rect,
            text=bubble_data.text,
            translated="",
            text_box=text_rect,
            layout_box=layout_box,
            text_class=bubble_data.text_class,
        )
        text_bubble.font_family = ""
        text_bubble.font_size = 0
        text_bubble.color = _color_to_hex(bubble_data.font_color)
        text_bubble.alignment = layout_plan.alignment
        text_bubble.writing_mode = getattr(layout_plan, "writing_mode", "horizontal")
        text_bubble.text_direction = getattr(layout_plan, "text_direction", "ltr")
        text_bubble.justification = getattr(layout_plan, "justification", "none")
        text_bubble.layout_padding = _insets_to_dict(getattr(layout_plan, "padding", None))
        text_bubble.layout_margin = _insets_to_dict(getattr(layout_plan, "margin", None))
        text_bubble.layout_confidence = float(getattr(layout_plan, "confidence", 0.0) or 0.0)
        text_bubble.layout_reasoning = getattr(layout_plan, "reasoning", "")
        bubbles.append(text_bubble)

    return bubbles


def merge_overlapping_bubbles(bubbles: list[TextBubble], iou_threshold: float = 0.25) -> list[TextBubble]:
    if len(bubbles) < 2:
        return bubbles

    def _iou(first: TextBubble, second: TextBubble) -> float:
        ax1, ay1 = first.box.x(), first.box.y()
        ax2, ay2 = ax1 + first.box.width(), ay1 + first.box.height()
        bx1, by1 = second.box.x(), second.box.y()
        bx2, by2 = bx1 + second.box.width(), by1 + second.box.height()
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = first.box.width() * first.box.height() + second.box.width() * second.box.height() - intersection
        if union <= 0:
            return 0.0
        return intersection / union

    from PySide6.QtCore import QRectF

    merged = True
    current = list(bubbles)
    while merged:
        merged = False
        i = 0
        while i < len(current):
            j = i + 1
            while j < len(current):
                if _iou(current[i], current[j]) >= iou_threshold:
                    first = current[i]
                    second = current[j]
                    x1 = min(first.box.x(), second.box.x())
                    y1 = min(first.box.y(), second.box.y())
                    x2 = max(first.box.x() + first.box.width(), second.box.x() + second.box.width())
                    y2 = max(first.box.y() + first.box.height(), second.box.y() + second.box.height())
                    first.box = QRectF(x1, y1, x2 - x1, y2 - y1)

                    if first.text_box is not None and second.text_box is not None:
                        tx1 = min(first.text_box.x(), second.text_box.x())
                        ty1 = min(first.text_box.y(), second.text_box.y())
                        tx2 = max(first.text_box.x() + first.text_box.width(), second.text_box.x() + second.text_box.width())
                        ty2 = max(first.text_box.y() + first.text_box.height(), second.text_box.y() + second.text_box.height())
                        first.text_box = QRectF(tx1, ty1, tx2 - tx1, ty2 - ty1)
                    elif second.text_box is not None:
                        first.text_box = QRectF(second.text_box)

                    if first.layout_box is not None and second.layout_box is not None:
                        lx1 = min(first.layout_box.x(), second.layout_box.x())
                        ly1 = min(first.layout_box.y(), second.layout_box.y())
                        lx2 = max(first.layout_box.x() + first.layout_box.width(), second.layout_box.x() + second.layout_box.width())
                        ly2 = max(first.layout_box.y() + first.layout_box.height(), second.layout_box.y() + second.layout_box.height())
                        first.layout_box = QRectF(lx1, ly1, lx2 - lx1, ly2 - ly1)
                    elif second.layout_box is not None:
                        first.layout_box = QRectF(second.layout_box)

                    merged_text = _join_merged_text([first.text, second.text])
                    if merged_text:
                        first.text = merged_text
                    merged_translation = _join_merged_text([first.translated, second.translated])
                    if merged_translation:
                        first.translated = merged_translation
                    current.pop(j)
                    merged = True
                    continue
                j += 1
            i += 1
    return current
