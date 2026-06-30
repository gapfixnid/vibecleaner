from typing import Tuple, List, Optional, cast
import logging
import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from app.models import TextBubble
from modules.rendering_wrapper import TextRenderer, TextLayoutResult
from modules.utils.image_utils import build_bubble_clip_mask

logger = logging.getLogger(__name__)


class RenderService:
    def __init__(self, renderer: Optional[TextRenderer] = None) -> None:
        self.renderer: TextRenderer = renderer or TextRenderer()

    def get_optimal_font(
        self, text: str, rect: QRectF, font_family: str | None = None
    ) -> Tuple[QFont, List[str], float]:
        """Finds the optimal font size, wrapped lines, and width for the given text bubble box."""
        if font_family is None:
            app = QApplication.instance()
            font_family = cast(QApplication, app).font().family() if app else "Segoe UI"
        return self.renderer.find_optimal_font_size(text, rect, font_family=font_family)

    def get_layout_for_bubble(
        self,
        text: str,
        bubble: TextBubble,
        image: np.ndarray | None = None,
        font_family: str | None = None,
    ) -> TextLayoutResult:
        if font_family is None:
            app = QApplication.instance()
            font_family = cast(QApplication, app).font().family() if app else "Segoe UI"

        mask = self._build_bubble_layout_mask(bubble, image)
        if mask is not None:
            return self.renderer.find_optimal_font_size_for_mask(text, bubble.box, mask, font_family=font_family)

        font, lines, render_width = self.renderer.find_optimal_font_size(text, bubble.box, font_family=font_family)
        alignment = getattr(bubble, 'alignment', 'center') or 'center'
        return self.renderer.layout_lines_in_rect(lines, bubble.box, font, render_width, alignment=alignment)

    def _build_bubble_layout_mask(self, bubble: TextBubble, image: np.ndarray | None) -> np.ndarray | None:
        if bubble.text_class == "text_free":
            return None

        rect = bubble.box
        width = int(round(rect.width()))
        height = int(round(rect.height()))
        if width <= 2 or height <= 2:
            return None

        inset = max(1, min(5, int(round(min(width, height) * 0.03))))
        fallback_mask = self.renderer.make_ellipse_mask(width, height, inset=inset)
        if image is None or bubble.text_box is None:
            return fallback_mask

        bounds = (
            int(round(rect.x())),
            int(round(rect.y())),
            int(round(rect.x() + rect.width())),
            int(round(rect.y() + rect.height())),
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
