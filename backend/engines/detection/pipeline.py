from typing import Optional

import logging
import numpy as np

from .backend import resolve_detection_backend
from .font.engine import extract_foreground_color
from .heuristic_lines import annotate_blocks_with_heuristic_lines
from .utils.content import filter_and_fix_bboxes
from ..common.geometry import does_rectangle_fit, do_rectangles_overlap, merge_overlapping_boxes
from ...infrastructure.runtime.device import resolve_device
from ..common.textblock import TextBlock

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """Common post-processing pipeline for all detection backends."""

    def __init__(self, settings=None, backend: str | None = None) -> None:
        self.settings = settings
        self.backend = resolve_detection_backend(backend)

    def build_text_blocks(
        self,
        image: np.ndarray,
        text_boxes: np.ndarray,
        bubble_boxes: Optional[np.ndarray] = None,
        bubbles_only: bool | None = None,
        line_merge_sensitivity: float | None = None,
        smart_direction: bool | None = None,
        text_direction_override: str | None = None,
        text_confidences: dict[tuple[int, int, int, int], float] | None = None,
    ) -> list[TextBlock]:
        text_boxes = filter_and_fix_bboxes(text_boxes, image.shape)
        bubble_boxes = filter_and_fix_bboxes(bubble_boxes, image.shape)
        text_boxes = merge_overlapping_boxes(text_boxes)

        if bubble_boxes is None:
            bubble_boxes = np.array([])
        if len(text_boxes) == 0:
            return []

        text_colors_per_box = self._extract_text_colors(image, text_boxes)
        text_blocks = self._match_text_to_bubbles(
            image,
            text_boxes,
            bubble_boxes,
            text_colors_per_box,
            text_confidences=text_confidences or {},
            bubbles_only=self._resolve_option("bubbles_only", bubbles_only, False),
        )
        self._annotate_lines(
            image,
            text_blocks,
            line_merge_sensitivity=self._resolve_option("line_merge_sensitivity", line_merge_sensitivity, 1.2),
            smart_direction=self._resolve_option("smart_direction", smart_direction, True),
            text_direction_override=self._resolve_option("text_direction_override", text_direction_override, "auto"),
        )
        return text_blocks

    def _resolve_option(self, name: str, explicit_value, default):
        if explicit_value is not None:
            return explicit_value
        if self.settings is not None and hasattr(self.settings, name):
            return getattr(self.settings, name)
        return default

    def _extract_text_colors(self, image: np.ndarray, text_boxes: np.ndarray) -> list[tuple]:
        h, w = image.shape[:2]
        text_colors_per_box: list[tuple] = [()] * len(text_boxes)
        for txt_idx, txt_box in enumerate(text_boxes):
            x1, y1, x2, y2 = map(int, txt_box)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 > x1 and y2 > y1:
                text_color = extract_foreground_color(image[y1:y2, x1:x2])
                if text_color is not None:
                    text_colors_per_box[txt_idx] = tuple(text_color)
        return text_colors_per_box

    def _is_bubble_background(self, image: np.ndarray, bbox: np.ndarray) -> bool:
        try:
            h_img, w_img = image.shape[:2]
            x1, y1, x2, y2 = map(int, bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)
            if x2 <= x1 or y2 <= y1:
                return False

            crop = image[y1:y2, x1:x2]
            h, w = crop.shape[:2]
            if h < 6 or w < 6:
                return False

            img = crop[:, :, :3]  # drop alpha channel if any

            # Sample border pixels to determine background color
            bw = max(2, min(h, w) // 8)
            if h <= bw * 2 or w <= bw * 2:
                return False

            top = img[:bw, bw:-bw] if w > bw * 2 else img[:bw, :]
            bottom = img[-bw:, bw:-bw] if w > bw * 2 else img[-bw:, :]
            left = img[bw:-bw, :bw]
            right = img[bw:-bw, -bw:]

            border_parts = []
            for part in (top, bottom, left, right):
                if part.size > 0:
                    border_parts.append(part.reshape(-1, 3))
            if not border_parts:
                return False

            border_pixels = np.concatenate(border_parts, axis=0).astype(np.float64)
            bg = np.median(border_pixels, axis=0)

            # Calculate luma (brightness)
            bg_luma = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]

            # Calculate standard deviation of luma to check uniformity
            border_luma = 0.299 * border_pixels[:, 0] + 0.587 * border_pixels[:, 1] + 0.114 * border_pixels[:, 2]
            bg_std = np.std(border_luma)

            # 1. White / Light speech bubbles: very bright background and relatively uniform
            if bg_luma >= 170 and bg_std <= 35:
                return True
            # 2. Dark speech bubbles: dark background and very uniform
            if bg_luma <= 95 and bg_std <= 25:
                return True

            return False
        except Exception:
            logger.exception("Failed to check bubble background. bbox=%s", bbox)
            return False

    def _match_text_to_bubbles(
        self,
        image: np.ndarray,
        text_boxes: np.ndarray,
        bubble_boxes: np.ndarray,
        text_colors_per_box: list[tuple],
        text_confidences: dict[tuple[int, int, int, int], float],
        bubbles_only: bool = False,
    ) -> list[TextBlock]:
        text_blocks = []
        text_matched = [False] * len(text_boxes)

        for txt_idx, txt_box in enumerate(text_boxes):
            text_color = text_colors_per_box[txt_idx]
            confidence = text_confidences.get(tuple(int(value) for value in txt_box))
            if len(bubble_boxes) == 0:
                text_blocks.append(TextBlock(
                    text_bbox=txt_box, text_class="text_free", font_color=text_color,
                    confidence=confidence,
                ))
                continue

            for bubble_box in bubble_boxes:
                if bubble_box is None:
                    continue
                if does_rectangle_fit(bubble_box, txt_box) or do_rectangles_overlap(bubble_box, txt_box):
                    # Check if it has a bubble-like background if bubbles_only is enabled
                    is_bubble_bg = True
                    if bubbles_only:
                        is_bubble_bg = self._is_bubble_background(image, bubble_box)

                    if is_bubble_bg:
                        text_blocks.append(
                            TextBlock(
                                text_bbox=txt_box,
                                bubble_bbox=bubble_box,
                                text_class="text_bubble",
                                font_color=text_color,
                                confidence=confidence,
                            )
                        )
                        text_matched[txt_idx] = True
                        break

            if not text_matched[txt_idx]:
                text_blocks.append(TextBlock(
                    text_bbox=txt_box, text_class="text_free", font_color=text_color,
                    confidence=confidence,
                ))

        return text_blocks

    def _annotate_lines(
        self,
        image: np.ndarray,
        text_blocks: list[TextBlock],
        line_merge_sensitivity: float = 1.2,
        smart_direction: bool = True,
        text_direction_override: str = "auto",
    ) -> None:
        try:
            device = resolve_device(self.settings.is_gpu_enabled(), self.backend) if self.settings else "cpu"
            _ = device
            annotate_blocks_with_heuristic_lines(
                image,
                text_blocks,
                line_merge_sensitivity=line_merge_sensitivity,
                smart_direction=smart_direction,
                text_direction_override=text_direction_override,
            )
        except Exception:
            logger.exception("Failed to build heuristic text lines. block_count=%s", len(text_blocks))
