from typing import Optional

import logging
import math
from dataclasses import dataclass
import numpy as np
from typing import Optional

from .backend import resolve_detection_backend
from .font.engine import extract_foreground_color
from .heuristic_lines import annotate_blocks_with_heuristic_lines
from .utils.content import filter_and_fix_bboxes
from ..common.geometry import does_rectangle_fit, do_rectangles_overlap
from ...infrastructure.runtime.device import resolve_device
from ..common.textblock import TextBlock
from ...infrastructure.model_catalog import DEFAULT_OCR_MODEL

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizedTextRegion:
    box: np.ndarray
    original_index: int
    confidence: float | None


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
        raw_text_count = len(text_boxes) if text_boxes is not None else 0
        raw_bubble_count = (
            len(bubble_boxes) if bubble_boxes is not None else 0
        )
        normalized_text = self._normalize_text_regions(
            text_boxes,
            image.shape,
            text_confidences or {},
        )
        normalized_bubbles = self._normalize_bubble_boxes(
            bubble_boxes,
            image.shape,
        )
        text_boxes = np.asarray(
            [region.box for region in normalized_text],
            dtype=int,
        ).reshape(-1, 4)
        bubble_boxes = np.asarray(
            normalized_bubbles,
            dtype=int,
        ).reshape(-1, 4)
        bubbles_only_enabled = self._resolve_option(
            "bubbles_only", bubbles_only, False
        )

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
            text_regions=normalized_text,
            bubbles_only=bubbles_only_enabled,
        )
        matched = sum(block.bubble_match_id is not None for block in text_blocks)
        ambiguous = sum(
            block.bubble_match_id is not None and block.ambiguous_match
            for block in text_blocks
        )
        unmatched = sum(block.bubble_match_id is None for block in text_blocks)
        diagnostics = {
            "invalid_box_ratio": (
                max(0, raw_text_count - len(text_boxes))
                + max(
                    0,
                    raw_bubble_count - len(bubble_boxes),
                )
            )
            / max(1, raw_text_count + raw_bubble_count),
            "ambiguous_match_ratio": ambiguous / max(1, matched),
            "unmatched_ratio": unmatched / max(1, len(text_blocks)),
            "matched": matched,
            "ambiguous": ambiguous,
            "unmatched": unmatched,
            "bubbles_only": float(bubbles_only_enabled),
        }
        for block in text_blocks:
            block.association_diagnostics = diagnostics
        self._annotate_lines(
            image,
            text_blocks,
            line_merge_sensitivity=self._resolve_option("line_merge_sensitivity", line_merge_sensitivity, 1.2),
            smart_direction=self._resolve_option("smart_direction", smart_direction, True),
            text_direction_override=self._resolve_option("text_direction_override", text_direction_override, "auto"),
        )
        return text_blocks

    @staticmethod
    def _normalize_text_regions(
        raw_boxes: np.ndarray,
        image_shape: tuple[int, ...],
        confidences: dict[tuple[int, int, int, int], float],
    ) -> list[NormalizedTextRegion]:
        regions: list[NormalizedTextRegion] = []
        source_boxes = raw_boxes if raw_boxes is not None else []
        for index, raw_box in enumerate(source_boxes):
            raw_key = tuple(int(value) for value in raw_box)
            cleaned = filter_and_fix_bboxes(
                [raw_box], image_shape
            )
            if len(cleaned) != 1:
                continue
            regions.append(
                NormalizedTextRegion(
                    box=np.asarray(cleaned[0], dtype=int),
                    original_index=index,
                    confidence=confidences.get(raw_key),
                )
            )
        return regions

    @staticmethod
    def _normalize_bubble_boxes(
        raw_boxes: np.ndarray | None,
        image_shape: tuple[int, ...],
    ) -> list[np.ndarray]:
        normalized: list[tuple[tuple[int, ...], int, np.ndarray]] = []
        source_boxes = raw_boxes if raw_boxes is not None else []
        for index, raw_box in enumerate(source_boxes):
            cleaned = filter_and_fix_bboxes(
                [raw_box], image_shape
            )
            if len(cleaned) != 1:
                continue
            box = np.asarray(cleaned[0], dtype=int)
            key = tuple(int(value) for value in box)
            normalized.append((key, index, box))
        normalized.sort(key=lambda item: (*item[0], item[1]))
        unique: dict[tuple[int, ...], np.ndarray] = {}
        for key, _original_index, box in normalized:
            unique.setdefault(key, box)
        return list(unique.values())

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
        text_regions: list[NormalizedTextRegion],
        bubbles_only: bool = False,
    ) -> list[TextBlock]:
        text_blocks = []
        text_matched = [False] * len(text_boxes)

        for txt_idx, txt_box in enumerate(text_boxes):
            text_color = text_colors_per_box[txt_idx]
            confidence = (
                text_regions[txt_idx].confidence
                if txt_idx < len(text_regions)
                else None
            )
            if len(bubble_boxes) == 0:
                text_blocks.append(TextBlock(
                    text_bbox=txt_box, text_class="text_free", font_color=text_color,
                    confidence=confidence,
                ))
                continue

            candidates: list[
                tuple[float, float, int, np.ndarray]
            ] = []
            text_x1, text_y1, text_x2, text_y2 = map(float, txt_box)
            text_area = max(1.0, (text_x2 - text_x1) * (text_y2 - text_y1))
            text_center_x = (text_x1 + text_x2) / 2.0
            text_center_y = (text_y1 + text_y2) / 2.0
            for bubble_match_id, bubble_box in enumerate(bubble_boxes):
                if bubble_box is None:
                    continue
                if does_rectangle_fit(bubble_box, txt_box) or do_rectangles_overlap(bubble_box, txt_box):
                    # Check if it has a bubble-like background if bubbles_only is enabled
                    is_bubble_bg = True
                    if bubbles_only:
                        is_bubble_bg = self._is_bubble_background(image, bubble_box)

                    if is_bubble_bg:
                        bx1, by1, bx2, by2 = map(float, bubble_box)
                        intersection = max(
                            0.0, min(text_x2, bx2) - max(text_x1, bx1)
                        ) * max(
                            0.0, min(text_y2, by2) - max(text_y1, by1)
                        )
                        overlap = intersection / text_area
                        center_inside = (
                            bx1 <= text_center_x <= bx2
                            and by1 <= text_center_y <= by2
                        )
                        if overlap < 0.5 and not center_inside:
                            continue
                        diagonal = max(
                            1.0,
                            float(np.hypot(bx2 - bx1, by2 - by1)),
                        )
                        distance = float(
                            np.hypot(
                                text_center_x - (bx1 + bx2) / 2.0,
                                text_center_y - (by1 + by2) / 2.0,
                            )
                        ) / diagonal
                        containment_bonus = (
                            1.0
                            if does_rectangle_fit(bubble_box, txt_box)
                            else 0.0
                        )
                        bubble_area = max(
                            1.0, (bx2 - bx1) * (by2 - by1)
                        )
                        area_ratio = bubble_area / text_area
                        oversized_penalty = max(
                            0.0, math.log2(area_ratio) - 4.0
                        ) * 0.35
                        candidates.append(
                            (
                                overlap * 3.0
                                + containment_bonus
                                + (1.5 if center_inside else 0.0)
                                - distance,
                                - oversized_penalty,
                                bubble_match_id,
                                bubble_box,
                            )
                        )

            if candidates:
                scored = [
                    (
                        score + penalty,
                        bubble_match_id,
                        bubble_box,
                    )
                    for score, penalty, bubble_match_id, bubble_box
                    in candidates
                ]
                scored.sort(key=lambda item: (-item[0], item[1]))
                best_score, bubble_match_id, bubble_box = scored[0]
                ambiguous = (
                    len(scored) > 1
                    and best_score - scored[1][0] < 0.25
                )
                text_blocks.append(
                    TextBlock(
                        text_bbox=txt_box,
                        bubble_bbox=bubble_box,
                        text_class="text_bubble",
                        font_color=text_color,
                        confidence=confidence,
                        bubble_match_id=bubble_match_id,
                        ambiguous_match=ambiguous,
                        problem_codes={
                            "BUBBLE_ASSOCIATION_UNCERTAIN"
                        }
                        if ambiguous
                        else None,
                    )
                )
                text_matched[txt_idx] = True

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
            from .ppocr_lines import annotate_blocks_with_ppocr_lines
            annotate_blocks_with_ppocr_lines(
                image,
                text_blocks,
                device=device,
                backend="onnx",
                det_model=getattr(self.settings, "ocr_model", DEFAULT_OCR_MODEL),
            )
        except Exception:
            logger.exception("PP-OCR line detection failed; using heuristic lines. block_count=%s", len(text_blocks))

        missing_lines = [block for block in text_blocks if not getattr(block, "lines", None)]
        if missing_lines:
            try:
                annotate_blocks_with_heuristic_lines(
                    image,
                    missing_lines,
                    line_merge_sensitivity=line_merge_sensitivity,
                    smart_direction=smart_direction,
                    text_direction_override=text_direction_override,
                )
            except Exception:
                logger.exception("Heuristic line fallback failed. block_count=%s", len(missing_lines))
