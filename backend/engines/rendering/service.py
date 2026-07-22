from typing import Any, Tuple, List, Optional, cast
import logging
import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from ...core.config import config_value
from ...core.models import Rect, TextBubble
from .renderer import TextRenderer, TextLayoutResult
from ...infrastructure.image.masks import build_bubble_clip_mask

logger = logging.getLogger(__name__)


def _to_qrectf(rect: Rect) -> QRectF:
    """Convert the core Rect DTO to Qt geometry at the rendering boundary."""
    return QRectF(rect.x, rect.y, rect.width, rect.height)


class RenderService:
    def __init__(self, renderer: Optional[TextRenderer] = None, config: Any = None) -> None:
        self.config = config
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
    ) -> Tuple[QFont, List[str], float]:
        """Finds the optimal font size, wrapped lines, and width for the given text bubble box."""
        if font_family is None:
            app = QApplication.instance()
            font_family = cast(QApplication, app).font().family() if app else "Segoe UI"
        return self.renderer.find_optimal_font_size(
            text,
            rect,
            font_family=font_family,
            min_size=self._min_font_size(),
            max_size=self._max_font_size(),
        )

    def get_layout_for_bubble(
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
        length_pressure = max(1.0, translated_length / source_length)
        source_weight = source_confidence / length_pressure
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

        return mask

    def _is_useful_shape_mask(self, mask: np.ndarray) -> bool:
        area_ratio = float(np.count_nonzero(mask)) / float(max(1, mask.size))
        return 0.25 <= area_ratio <= 0.92
