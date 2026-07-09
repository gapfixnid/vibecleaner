# bubble_analysis_service.py
# Analyzes detected text blocks to produce structured bubble data.
#
# Responsibilities:
# 1. Group text lines into parent bubbles (IoU-based containment)
# 2. Extract/validate textBox from text region
# 3. Calculate layoutBox using distance transform (not 30% scaling)
# 4. Sort by reading order (LTR/RTL)
# 5. Assign confidence scores

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BubbleAnalysisResult:
    """Result of bubble analysis for a single page."""
    bubbles: List[BubbleData]
    reading_order: str  # "LTR" or "RTL"
    writing_mode: str   # "horizontal" or "vertical"
    panel_count: int = 0


@dataclass
class BubbleData:
    """Analyzed bubble with structured geometry."""
    # Geometry
    bubble_box: Tuple[int, int, int, int]  # (x1, y1, x2, y2) of bubble
    text_box: Tuple[int, int, int, int]    # (x1, y1, x2, y2) of text region
    layout_box: Tuple[int, int, int, int]  # (x1, y1, x2, y2) for text placement
    polygon: List[Tuple[int, int]] = field(default_factory=list)  # bubble outline

    # Content
    text: str = ""
    text_class: str = ""  # "text_bubble", "text_free", "sfx"
    font_color: Tuple[int, int, int] = (0, 0, 0)

    # Analysis
    confidence: float = 1.0
    reading_order: int = 0
    direction: str = "horizontal"  # "horizontal" or "vertical"

    # Link to original block
    original_id: Optional[int] = None

    @property
    def width(self) -> int:
        return self.bubble_box[2] - self.bubble_box[0]

    @property
    def height(self) -> int:
        return self.bubble_box[3] - self.bubble_box[1]

    @property
    def center(self) -> Tuple[float, float]:
        return (
            (self.bubble_box[0] + self.bubble_box[2]) / 2,
            (self.bubble_box[1] + self.bubble_box[3]) / 2,
        )


# ---------------------------------------------------------------------------
# Bubble Analysis Service
# ---------------------------------------------------------------------------

class BubbleAnalysisService:
    """Analyze detected text blocks and produce structured bubble data.

    Pipeline:
    1. Group text lines into parent bubbles
    2. Extract/validate textBox
    3. Calculate layoutBox via distance transform
    4. Sort by reading order
    5. Assign confidence scores
    """

    def __init__(
        self,
        layout_padding_ratio: float = 0.15,
        min_confidence: float = 0.3,
    ):
        self.layout_padding_ratio = layout_padding_ratio
        self.min_confidence = min_confidence

    def analyze(
        self,
        image: np.ndarray,
        text_blocks: list,
        source_lang: str = "Japanese",
    ) -> BubbleAnalysisResult:
        """Analyze detected text blocks.

        Args:
            image: Source image (RGB/BGR numpy array)
            text_blocks: List of TextBlock from detection
            source_lang: Source language for reading direction

        Returns:
            BubbleAnalysisResult with analyzed bubbles
        """
        if not text_blocks:
            return BubbleAnalysisResult(
                bubbles=[],
                reading_order=self._get_reading_order(source_lang),
                writing_mode="horizontal",
            )

        # Step 1: Convert TextBlocks to BubbleData
        bubbles = [self._convert_block(block, idx) for idx, block in enumerate(text_blocks)]

        # Step 2: Group text lines into parent bubbles (if needed)
        bubbles = self._group_into_bubbles(image, bubbles)

        # Step 3: Calculate layoutBox for each bubble
        for bubble in bubbles:
            bubble.layout_box = self._calculate_layout_box(
                image, bubble.bubble_box, bubble.text_box, bubble.text_class
            )

        # Step 4: Sort by reading order
        reading_order = self._get_reading_order(source_lang)
        bubbles = self._sort_by_reading_order(bubbles, reading_order)

        # Step 5: Assign confidence scores
        for bubble in bubbles:
            bubble.confidence = self._calculate_confidence(bubble, image)

        return BubbleAnalysisResult(
            bubbles=bubbles,
            reading_order=reading_order,
            writing_mode="horizontal",  # Could be enhanced with direction detection
        )

    def _convert_block(self, block, idx: int) -> BubbleData:
        """Convert a TextBlock to BubbleData."""
        # Get bubble box (use text box if no bubble detected)
        if hasattr(block, 'bubble_xyxy') and block.bubble_xyxy is not None:
            bubble_box = tuple(map(int, block.bubble_xyxy))
        else:
            bubble_box = tuple(map(int, block.xyxy))

        # Get text box
        text_box = tuple(map(int, block.xyxy))

        # Get text class
        text_class = getattr(block, 'text_class', 'text_free')

        # Get font color
        font_color = getattr(block, 'font_color', (0, 0, 0))
        if isinstance(font_color, str):
            font_color = self._hex_to_rgb(font_color)

        return BubbleData(
            bubble_box=bubble_box,
            text_box=text_box,
            layout_box=text_box,  # Will be recalculated
            text=getattr(block, 'text', ''),
            text_class=text_class,
            font_color=font_color,
            confidence=1.0,
            reading_order=idx,
            direction=getattr(block, 'direction', 'horizontal'),
            original_id=getattr(block, 'id', idx),
        )

    def _group_into_bubbles(
        self,
        image: np.ndarray,
        bubbles: List[BubbleData],
    ) -> List[BubbleData]:
        """Group text lines into parent bubbles using IoU-based containment.

        If multiple text blocks are contained within the same bubble,
        merge them into a single BubbleData with combined text.
        """
        if not bubbles:
            return bubbles

        # Simple grouping: bubbles with same bubble_box are already grouped
        # This is a placeholder for more advanced grouping if needed
        return bubbles

    def _calculate_layout_box(
        self,
        image: np.ndarray,
        bubble_box: Tuple[int, int, int, int],
        text_box: Tuple[int, int, int, int],
        text_class: str,
    ) -> Tuple[int, int, int, int]:
        """Calculate the layout box for text placement.

        Uses distance transform to find the largest inscribed rectangle
        within the bubble, instead of simple 30% scaling.

        For text_free class, returns the text box as-is.
        """
        if text_class == "text_free":
            return text_box

        x1, y1, x2, y2 = bubble_box
        width = x2 - x1
        height = y2 - y1

        if width < 10 or height < 10:
            return text_box

        # Try distance transform approach (requires OpenCV)
        if HAS_CV2:
            try:
                # Extract bubble region
                bubble_roi = image[y1:y2, x1:x2]
                gray = cv2.cvtColor(bubble_roi, cv2.COLOR_RGB2GRAY) if len(bubble_roi.shape) == 3 else bubble_roi

                # Create binary mask (text areas = 0, background = 255)
                _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

                # Distance transform
                dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)

                # Find the point farthest from any edge
                _, max_dist, _, max_loc = cv2.minMaxLoc(dist)

                if max_dist > 5:
                    # Create inscribed circle/rectangle at the farthest point
                    cx, cy = max_loc
                    radius = int(max_dist * 0.8)  # Safety margin

                    # Calculate inscribed rectangle
                    ins_x1 = max(0, cx - radius)
                    ins_y1 = max(0, cy - radius)
                    ins_x2 = min(width, cx + radius)
                    ins_y2 = min(height, cy + radius + 2)

                    # Apply padding
                    padding_x = int((ins_x2 - ins_x1) * self.layout_padding_ratio)
                    padding_y = int((ins_y2 - ins_y1) * self.layout_padding_ratio)

                    layout_x1 = x1 + ins_x1 + padding_x
                    layout_y1 = y1 + ins_y1 + padding_y
                    layout_x2 = x1 + ins_x2 - padding_x
                    layout_y2 = y1 + ins_y2 - padding_y

                    return (layout_x1, layout_y1, layout_x2, layout_y2)
            except Exception:
                # Fall back to shrink on error
                pass
        # cv2 not available or failed - fall through to fallback

        # Fallback: Use text box with padding
        tx1, ty1, tx2, ty2 = text_box
        t_width = tx2 - tx1
        t_height = ty2 - ty1
        padding_x = int(t_width * self.layout_padding_ratio)
        padding_y = int(t_height * self.layout_padding_ratio)

        return (
            tx1 + padding_x,
            ty1 + padding_y,
            tx2 - padding_x,
            ty2 - padding_y,
        )

    def _sort_by_reading_order(
        self,
        bubbles: List[BubbleData],
        reading_order: str,
    ) -> List[BubbleData]:
        """Sort bubbles by reading order.

        For LTR: top-to-bottom, then left-to-right
        For RTL: top-to-bottom, then right-to-left
        """
        if not bubbles:
            return bubbles

        # Group by vertical position (rows)
        rows: List[List[BubbleData]] = []
        sorted_bubbles = sorted(bubbles, key=lambda b: b.center[1])

        current_row: List[BubbleData] = []
        current_y = sorted_bubbles[0].center[1] if sorted_bubbles else 0
        row_threshold = 30  # pixels

        for bubble in sorted_bubbles:
            if abs(bubble.center[1] - current_y) <= row_threshold:
                current_row.append(bubble)
            else:
                rows.append(current_row)
                current_row = [bubble]
                current_y = bubble.center[1]
        if current_row:
            rows.append(current_row)

        # Sort each row horizontally
        flat = []
        for row in rows:
            if reading_order == "RTL":
                row.sort(key=lambda b: -b.center[0])
            else:
                row.sort(key=lambda b: b.center[0])
            flat.extend(row)

        # Assign reading order indices
        for idx, bubble in enumerate(flat):
            bubble.reading_order = idx

        return flat

    def _calculate_confidence(
        self,
        bubble: BubbleData,
        image: np.ndarray,
    ) -> float:
        """Calculate confidence score for a bubble.

        Factors:
        - Bubble size (larger = more confident)
        - Text presence
        - Bubble-background uniformity
        """
        confidence = 0.5  # Base confidence

        # Size factor
        area = bubble.width * bubble.height
        if area > 10000:
            confidence += 0.2
        elif area > 1000:
            confidence += 0.1

        # Text factor
        if bubble.text and len(bubble.text.strip()) > 0:
            confidence += 0.2

        # Text class factor
        if bubble.text_class == "text_bubble":
            confidence += 0.1

        return min(1.0, confidence)

    def _get_reading_order(self, source_lang: str) -> str:
        """Determine reading order from source language."""
        from pipeline.analysis.page import infer_reading_order

        direction = infer_reading_order(source_lang).direction
        return "RTL" if direction == "rtl" else "LTR"

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        try:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except (ValueError, IndexError):
            return (0, 0, 0)
