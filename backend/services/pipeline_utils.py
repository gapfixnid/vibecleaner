import numpy as np
from app.models import TextBubble
from modules.config import config

def _inpaint_boxes(bubbles) -> list:
    if config.inpaint_use_textbox_only:
        return [b.source_xyxy() for b in bubbles]
    boxes = []
    for b in bubbles:
        box = b.box
        boxes.append([box.x(), box.y(), box.x() + box.width(), box.y() + box.height()])
    return boxes

def _bubble_clip_boxes(bubbles) -> list:
    boxes = []
    for b in bubbles:
        box = b.box
        boxes.append([box.x(), box.y(), box.x() + box.width(), box.y() + box.height()])
    return boxes

def _rect_from_xyxy(xyxy):
    from PySide6.QtCore import QRectF
    x1, y1, x2, y2 = map(int, xyxy)
    return QRectF(x1, y1, x2 - x1, y2 - y1)

def _bubbles_from_analysis(
    image: np.ndarray,
    blocks: list,
    source_lang: str,
    target_lang: str,
    page_analysis_service,
    bubble_analysis_service,
    layout_planner_service
) -> list:
    from services.layout_planner_service import BubbleLayoutInput

    # 1. Page Analysis
    page_result = page_analysis_service.analyze(image, source_lang=source_lang, text_blocks=blocks)

    # 2. Bubble Analysis
    bubble_result = bubble_analysis_service.analyze(image, blocks, source_lang=source_lang)

    if not bubble_result.bubbles:
        return []

    # 3. Convert BubbleData -> TextBubble with layout planning
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
            page_reading_order=page_result.reading_order.direction if hasattr(page_result.reading_order, 'direction') else page_result.reading_order,
            page_writing_mode=page_result.writing_mode,
        )
        layout_plan = layout_planner_service.plan(layout_inp)

        tb = TextBubble(
            id=idx + 1,
            box=bubble_rect,
            text=bd.text,
            translated="",
            text_box=text_rect,
            text_class=bd.text_class,
        )
        tb.font_family = "Pretendard Variable"
        tb.font_size = 0
        if hasattr(bd, "font_color") and isinstance(bd.font_color, tuple) and len(bd.font_color) == 3:
            tb.color = f"#{bd.font_color[0]:02x}{bd.font_color[1]:02x}{bd.font_color[2]:02x}"
        else:
            tb.color = "#000000"
        tb.alignment = layout_plan.alignment

        bubbles.append(tb)

    return bubbles

def _merge_overlapping_bubbles(bubbles: list[TextBubble], iou_threshold: float = 0.25) -> list[TextBubble]:
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
                    texts = [t for t in (ai.text, aj.text) if t and t.strip()]
                    ai.text = ' '.join(texts) if texts else ai.text
                    translations = [t for t in (ai.translated, aj.translated) if t and t.strip()]
                    ai.translated = ' '.join(translations) if translations else ai.translated
                    current.pop(j)
                    merged = True
                    continue
                j += 1
            i += 1
    return current
