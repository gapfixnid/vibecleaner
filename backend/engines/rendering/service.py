from dataclasses import dataclass
import math
from typing import Any, Tuple, List, Optional
import logging
import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QGuiApplication
from ...core.config import config_value
from ...core.models import Rect, TextBubble
from .renderer import TextRenderer, TextLayoutResult
from ...infrastructure.runtime.qt import QtRenderExecutor, QtWorkerState, get_qt_runtime
from ...infrastructure.image.masks import build_bubble_clip_mask

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FontDescriptor:
    family_name: str
    pixel_size: int
    bold: bool = False
    italic: bool = False

    # Compatibility helpers for callers that used the old QFont result.
    def family(self) -> str:
        return self.family_name

    def pixelSize(self) -> int:
        return self.pixel_size


@dataclass(frozen=True)
class PublicTextLayoutResult:
    font: FontDescriptor
    lines: list[str]
    render_width: float
    line_layouts: list[Any]
    score: float = 0.0
    is_overflow: bool = False
    reached_min_font: bool = False
    line_height_ratio: float = 1.0
    area_usage: float = 0.0


def _to_qrectf(rect: Rect) -> QRectF:
    """Convert the core Rect DTO to Qt geometry at the rendering boundary."""
    return QRectF(rect.x, rect.y, rect.width, rect.height)


class RenderService:
    def __init__(
        self,
        renderer: Optional[TextRenderer] = None,
        config: Any = None,
        executor: QtRenderExecutor | None = None,
    ) -> None:
        self.config = config
        self.executor = executor or get_qt_runtime().executor
        self.renderer: TextRenderer = renderer or TextRenderer(
            min_font_size=self._min_font_size(),
            max_font_size=self._max_font_size(),
        )

    def _min_font_size(self) -> float:
        return float(config_value(self.config, "min_font_size"))

    def _max_font_size(self) -> float:
        return float(config_value(self.config, "max_font_size"))

    def _automatic_min_font_size(self, image: np.ndarray | None) -> float:
        configured = self._min_font_size()
        if image is None or image.ndim < 2:
            return configured
        page_short_side = float(min(image.shape[:2]))
        scaled_floor = max(11.0, min(24.0, page_short_side * 0.009))
        return min(self._max_font_size(), max(configured, scaled_floor))

    def get_optimal_font(
        self, text: str, rect: QRectF, font_family: str | None = None
    ) -> Tuple[FontDescriptor, List[str], float]:
        """Finds the optimal font size, wrapped lines, and width for the given text bubble box."""
        def task(_worker: QtWorkerState):
            resolved_family = font_family
            if resolved_family is None:
                app = QGuiApplication.instance()
                resolved_family = app.font().family() if app else "Segoe UI"
            font, lines, width = self.renderer.find_optimal_font_size(
                text,
                rect,
                font_family=resolved_family,
                min_size=self._min_font_size(),
                max_size=self._max_font_size(),
            )
            return FontDescriptor(font.family(), font.pixelSize(), font.bold(), font.italic()), lines, width

        return self.executor.run(task)

    def get_layout_for_bubble(
        self,
        text: str,
        bubble: TextBubble,
        image: np.ndarray | None = None,
        font_family: str | None = None,
    ) -> PublicTextLayoutResult:
        return self.executor.run(
            lambda worker: self._serialize_layout(
                self._get_layout_for_bubble_worker(
                    text,
                    bubble,
                    image=image,
                    font_family=font_family,
                )
            )
        )

    def _get_layout_for_bubble_worker(
        self,
        text: str,
        bubble: TextBubble,
        image: np.ndarray | None = None,
        font_family: str | None = None,
    ) -> TextLayoutResult:
        layout_rect = self._text_layout_rect(bubble)
        mask = self._build_bubble_layout_mask(bubble, image)
        alignment = getattr(bubble, 'alignment', 'center') or 'center'
        requested_font_size = int(getattr(bubble, "font_size", 0) or 0)
        padding = dict(getattr(bubble, "layout_padding", {}) or {})
        margin = dict(getattr(bubble, "layout_margin", {}) or {})
        target_center_y = self._target_center_y(text, bubble, mask)
        automatic_min_size = self._automatic_min_font_size(image)

        if requested_font_size > 0:
            fixed_rect = _to_qrectf(bubble.box) if mask is not None else layout_rect
            layout = self.renderer.layout_text_at_fixed_size(
                text,
                fixed_rect,
                requested_font_size,
                mask=mask,
                font_family=font_family,
                alignment=alignment,
                padding=padding,
                margin=margin,
                target_center_y=target_center_y,
            )
            return layout

        if mask is not None:
            layout = self.renderer.find_optimal_font_size_for_mask(
                text,
                _to_qrectf(bubble.box),
                mask,
                font_family=font_family,
                min_size=automatic_min_size,
                max_size=self._max_font_size(),
                alignment=alignment,
                padding=padding,
                margin=margin,
                target_center_y=target_center_y,
            )
            return layout

        return self.renderer.find_optimal_layout_in_rect(
            text,
            layout_rect,
            font_family=font_family,
            min_size=automatic_min_size,
            max_size=self._max_font_size(),
            alignment=alignment,
            padding=padding,
            margin=margin,
        )

    @staticmethod
    def _serialize_layout(layout: TextLayoutResult) -> PublicTextLayoutResult:
        font = layout.font
        def font_value(name: str, default: Any) -> Any:
            value = getattr(font, name, None)
            return value() if callable(value) else default

        pixel_size = int(font_value("pixelSize", -1) or -1)
        if pixel_size <= 0:
            point_size = float(font_value("pointSizeF", 9.0) or 9.0)
            pixel_size = max(1, int(round(point_size * 96.0 / 72.0)))
        return PublicTextLayoutResult(
            font=FontDescriptor(
                str(font_value("family", "Segoe UI")),
                pixel_size,
                bool(font_value("bold", False)),
                bool(font_value("italic", False)),
            ),
            lines=list(getattr(layout, "lines", [])),
            render_width=float(getattr(layout, "render_width", 0.0)),
            line_layouts=list(layout.line_layouts),
            score=float(getattr(layout, "score", 0.0)),
            is_overflow=bool(getattr(layout, "is_overflow", False)),
            reached_min_font=bool(getattr(layout, "reached_min_font", False)),
            line_height_ratio=float(getattr(layout, "line_height_ratio", 1.0)),
            area_usage=float(getattr(layout, "area_usage", 0.0)),
        )

    def _target_center_y(
        self,
        text: str,
        bubble: TextBubble,
        mask: np.ndarray | None,
    ) -> float | None:
        if mask is None:
            return None
        mask_ys = np.where(np.asarray(mask) > 0)[0]
        mask_center = (
            bubble.box.y + float(np.mean(mask_ys))
            if mask_ys.size
            else bubble.box.y + bubble.box.height / 2.0
        )
        text_box = bubble.text_box
        if text_box is None or text_box.width <= 1 or text_box.height <= 1:
            return mask_center

        source_center = text_box.y + text_box.height / 2.0
        source_confidence = max(0.0, min(1.0, float(bubble.layout_confidence or 0.0)))
        source_length = max(1, len((bubble.text or "").strip()))
        translated_length = max(1, len((text or "").strip()))
        length_ratio = translated_length / source_length
        source_weight = 0.6 if source_confidence >= 0.7 and 0.8 <= length_ratio <= 1.25 else 0.2
        return mask_center * (1.0 - source_weight) + source_center * source_weight

    def _text_layout_rect(self, bubble: TextBubble) -> QRectF:
        rect = bubble.layout_box if bubble.layout_box is not None else bubble.box
        if rect.width <= 1 or rect.height <= 1:
            return _to_qrectf(bubble.box)
        return _to_qrectf(rect)

    def _build_bubble_layout_mask(self, bubble: TextBubble, image: np.ndarray | None) -> np.ndarray | None:
        if bubble.text_class == "text_free":
            return None

        rect = bubble.box
        width = int(round(rect.width))
        height = int(round(rect.height))
        if width <= 2 or height <= 2:
            return None

        inset = max(1, min(5, int(round(min(width, height) * 0.03))))
        fallback_mask = self.renderer.make_ellipse_mask(width, height, inset=inset)
        if image is None or bubble.text_box is None:
            return fallback_mask

        bounds = (
            int(round(rect.x)),
            int(round(rect.y)),
            int(round(rect.right)),
            int(round(rect.bottom)),
        )
        coords = [int(round(v)) for v in bubble.source_xyxy()]
        seed_bbox = (coords[0], coords[1], coords[2], coords[3]) if len(coords) == 4 else None
        try:
            mask = build_bubble_clip_mask(
                (height, width),
                bounds,
                bounds,
                inset=inset,
                image=image,
                seed_bbox=seed_bbox,
            )
        except Exception:
            logger.exception(
                "Failed to build bubble layout mask; falling back to ellipse mask. bubble_id=%s",
                getattr(bubble, "id", None),
            )
            return fallback_mask

        if mask is None or not bool(np.asarray(mask).any()):
            return fallback_mask

        mask = np.asarray(mask, dtype=np.uint8)
        if not self._is_useful_shape_mask(mask):
            return fallback_mask
        return self._refine_shape_mask(mask, bubble)

    def _refine_shape_mask(self, raw_mask: np.ndarray, bubble: TextBubble) -> np.ndarray:
        """Keep the component that best represents the usable bubble body."""
        import cv2

        raw = (np.asarray(raw_mask) > 0).astype(np.uint8)
        height, width = raw.shape
        short_side = max(1, min(width, height))
        distance = cv2.distanceTransform(raw, cv2.DIST_L2, 5)
        core = distance >= max(2.0, short_side * 0.04)
        opening_size = min(15, max(1, int(round(short_side * 0.06))))
        if opening_size % 2 == 0:
            opening_size += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (opening_size, opening_size))
        opened = cv2.morphologyEx(raw, cv2.MORPH_OPEN, kernel)
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(opened, 8)
        if count <= 1:
            return raw_mask

        text_box = bubble.text_box
        if text_box is not None:
            tx1 = max(0, int(math.floor(text_box.x - bubble.box.x)))
            ty1 = max(0, int(math.floor(text_box.y - bubble.box.y)))
            tx2 = min(width, int(math.ceil(text_box.right - bubble.box.x)))
            ty2 = min(height, int(math.ceil(text_box.bottom - bubble.box.y)))
        else:
            tx1, ty1, tx2, ty2 = width // 4, height // 4, width * 3 // 4, height * 3 // 4
        text_region = np.zeros_like(raw, dtype=bool)
        if tx2 > tx1 and ty2 > ty1:
            text_region[ty1:ty2, tx1:tx2] = True
        text_area = max(1, int(text_region.sum()))
        core_area = max(1, int(core.sum()))
        raw_area = max(1, int(raw.sum()))
        text_center = np.array([(tx1 + tx2) / 2.0, (ty1 + ty2) / 2.0])
        diagonal = max(1.0, math.hypot(width, height))
        best_label = 1
        best_score = -float("inf")
        for label in range(1, count):
            component = labels == label
            core_overlap = float(np.count_nonzero(component & core)) / core_area
            text_overlap = float(np.count_nonzero(component & text_region)) / text_area
            area_ratio = float(stats[label, cv2.CC_STAT_AREA]) / raw_area
            distance_to_text = float(np.linalg.norm(centroids[label] - text_center)) / diagonal
            score = core_overlap * 4.0 + text_overlap * 3.0 + area_ratio - distance_to_text
            if score > best_score:
                best_score = score
                best_label = label
        selected = (labels == best_label).astype(np.uint8)
        closing_size = max(1, int(round(short_side * 0.03)))
        if closing_size % 2 == 0:
            closing_size += 1
        closing_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (closing_size, closing_size))
        selected = cv2.morphologyEx(selected, cv2.MORPH_CLOSE, closing_kernel)
        if int(selected.sum()) < raw_area * 0.45:
            return raw_mask
        return (selected * 255).astype(np.uint8)

    def _is_useful_shape_mask(self, mask: np.ndarray) -> bool:
        area_ratio = float(np.count_nonzero(mask)) / float(max(1, mask.size))
        return 0.25 <= area_ratio <= 0.92
