# layout_planner_service.py
# Layout Planner — decide layout properties before typesetting.
#
# Pipeline:
#   Bubble Analysis -> Layout Planner -> Typesetter -> Renderer
#
# Determines:
#   - alignment (left | center | right | justify)
#   - padding (Insets)
#   - margin (Insets)
#   - writing_mode (horizontal | vertical)
#   - justification (none | full | distributed)
#   - anchor_point (where text starts within layout box)

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QRectF

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Insets:
    """Four-sided inset values (top, right, bottom, left)."""
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    def horizontal(self) -> float:
        return self.left + self.right

    def vertical(self) -> float:
        return self.top + self.bottom

    def to_dict(self) -> Dict[str, float]:
        return {"top": self.top, "right": self.right, "bottom": self.bottom, "left": self.left}


@dataclass
class Point:
    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}


@dataclass
class LayoutPlanDto:
    """Layout plan for a single bubble — produced by Layout Planner, consumed by Typesetter."""
    alignment: str = 'center'  # 'left' | 'center' | 'right' | 'justify'
    padding: Insets = field(default_factory=Insets)
    margin: Insets = field(default_factory=Insets)
    writing_mode: str = 'horizontal'  # 'horizontal' | 'vertical'
    justification: str = 'none'  # 'none' | 'full' | 'distributed'
    anchor_point: Point = field(default_factory=Point)
    text_direction: str = 'ltr'  # 'ltr' | 'rtl'
    confidence: float = 0.0
    reasoning: str = ''

    def to_dict(self) -> dict:
        return {
            'alignment': self.alignment,
            'padding': self.padding.to_dict(),
            'margin': self.margin.to_dict(),
            'writing_mode': self.writing_mode,
            'justification': self.justification,
            'anchor_point': self.anchor_point.to_dict(),
            'text_direction': self.text_direction,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
        }


# ---------------------------------------------------------------------------
# Bubble input (lightweight, no circular dependency)
# ---------------------------------------------------------------------------

@dataclass
class BubbleLayoutInput:
    """Input for layout planning — derived from BubbleData or TextBubble."""
    bubble_box: QRectF  # Full bubble bounding box
    layout_box: QRectF  # Area where text can be placed
    text: str = ''  # Text to render
    text_class: str = ''  # 'text_bubble' | 'text_free' | 'sfx'
    polygon: Optional[np.ndarray] = None  # Bubble polygon for shape analysis
    # Page-level context
    page_reading_order: str = 'ltr'
    page_writing_mode: str = 'horizontal'
    # User overrides
    user_alignment: Optional[str] = None
    user_font_size: int = 0


# ---------------------------------------------------------------------------
# Layout Planner Service
# ---------------------------------------------------------------------------

class LayoutPlannerService:
    """Decide layout properties before typesetting.

    Sits between Bubble Analysis and Typesetter:
        Bubble Analysis -> Layout Planner -> Typesetter

    Determines alignment, padding, margin, writing mode, justification,
    and anchor point based on bubble geometry, text characteristics,
    and page-level reading direction.
    """

    # Bubble shape categories for alignment decisions
    SHAPE_WIDE_THRESHOLD = 2.0  # width/height ratio for "wide" bubbles
    SHAPE_TALL_THRESHOLD = 0.5  # width/height ratio for "tall" bubbles

    # Padding ratios relative to layout box dimensions
    PADDING_RATIO_X = 0.08  # 8% of width
    PADDING_RATIO_Y = 0.06  # 6% of height
    MIN_PADDING = 2.0
    MAX_PADDING_X = 16.0
    MAX_PADDING_Y = 12.0

    # Margin ratios for text-free areas
    MARGIN_RATIO = 0.03  # 3% of dimension

    def __init__(self):
        pass

    def plan(
        self,
        input: BubbleLayoutInput,
        bubble_image: Optional[np.ndarray] = None,
    ) -> LayoutPlanDto:
        """Create a layout plan for a bubble.

        Args:
            input: Bubble layout input with box, text, and page context
            bubble_image: Optional bubble region for shape analysis

        Returns:
            LayoutPlanDto with all layout decisions
        """
        plan = LayoutPlanDto()
        reasoning_parts = []

        # 1. Writing mode (from page analysis or per-bubble inference)
        plan.writing_mode = self._determine_writing_mode(input)
        reasoning_parts.append(f"writing_mode={plan.writing_mode}")

        # 2. Text direction (from page reading order)
        plan.text_direction = self._determine_text_direction(input)
        reasoning_parts.append(f"direction={plan.text_direction}")

        # 3. Alignment (shape-aware + text-aware + user override)
        plan.alignment = self._determine_alignment(input)
        reasoning_parts.append(f"alignment={plan.alignment}")

        # 4. Padding (proportional to bubble size)
        plan.padding = self._determine_padding(input)
        reasoning_parts.append(
            f"padding=({plan.padding.top:.0f},{plan.padding.right:.0f},"
            f"{plan.padding.bottom:.0f},{plan.padding.left:.0f})"
        )

        # 5. Margin (small additional spacing)
        plan.margin = self._determine_margin(input)

        # 6. Justification (based on alignment + text length)
        plan.justification = self._determine_justification(input, plan.alignment)
        reasoning_parts.append(f"justification={plan.justification}")

        # 7. Anchor point (where text starts)
        plan.anchor_point = self._determine_anchor_point(input, plan)
        reasoning_parts.append(
            f"anchor=({plan.anchor_point.x:.0f},{plan.anchor_point.y:.0f})"
        )

        # Confidence: based on how many signals aligned
        plan.confidence = self._calculate_confidence(input, plan)
        plan.reasoning = '; '.join(reasoning_parts)

        return plan

    def plan_batch(
        self,
        inputs: List[BubbleLayoutInput],
    ) -> List[LayoutPlanDto]:
        """Create layout plans for multiple bubbles.

        Bubbles are planned independently but share page-level context.
        """
        return [self.plan(inp) for inp in inputs]

    # -------------------------------------------------------------------
    # Writing mode
    # -------------------------------------------------------------------

    def _determine_writing_mode(self, inp: BubbleLayoutInput) -> str:
        """Determine writing mode for text.

        Priority: page_writing_mode > bubble aspect ratio > default
        """
        # Use page-level writing mode as primary signal
        if inp.page_writing_mode == 'vertical':
            return 'vertical'

        # Check if bubble is tall (vertical text often in tall bubbles)
        aspect = inp.layout_box.width() / max(1, inp.layout_box.height())
        if aspect < self.SHAPE_TALL_THRESHOLD:
            return 'vertical'

        return 'horizontal'

    # -------------------------------------------------------------------
    # Text direction
    # -------------------------------------------------------------------

    def _determine_text_direction(self, inp: BubbleLayoutInput) -> str:
        """Determine text flow direction.

        Based on page reading order: RTL pages have RTL text flow.
        """
        return inp.page_reading_order if inp.page_reading_order in ('ltr', 'rtl') else 'ltr'

    # -------------------------------------------------------------------
    # Alignment
    # -------------------------------------------------------------------

    def _determine_alignment(self, inp: BubbleLayoutInput) -> str:
        """Determine text alignment within layout box.

        Priority: user override > shape-based > text-based > default
        """
        # 1. User override always wins
        if inp.user_alignment and inp.user_alignment in ('left', 'center', 'right', 'justify'):
            return inp.user_alignment

        # 2. Text-free bubbles: align based on position
        if inp.text_class == 'text_free':
            return self._align_text_free(inp)

        # 3. SFX: center by default
        if inp.text_class == 'sfx':
            return 'center'

        # 4. Shape-based alignment for speech bubbles
        return self._align_by_shape(inp)

    def _align_text_free(self, inp: BubbleLayoutInput) -> str:
        """Align text-free elements based on position and shape."""
        # Check if text is positioned to the right or left of layout box
        bw = inp.bubble_box.width()
        lw = inp.layout_box.width()
        if bw > lw * 2:
            # Wide bubble with narrow text area — likely sidebar text
            rel_x = inp.layout_box.x() - inp.bubble_box.x()
            if rel_x < bw * 0.5:
                return 'left'
            return 'right'
        return 'center'

    def _align_by_shape(self, inp: BubbleLayoutInput) -> str:
        """Align based on bubble shape and text characteristics."""
        aspect = inp.layout_box.width() / max(1, inp.layout_box.height())
        text = inp.text or ''

        # Tall narrow bubbles: center
        if aspect < self.SHAPE_TALL_THRESHOLD:
            return 'center'

        # Very wide bubbles with short text: center
        if aspect > self.SHAPE_WIDE_THRESHOLD and len(text) < 20:
            return 'center'

        # Wide bubbles with long text: consider justification
        if aspect > 1.5 and len(text) > 30:
            return 'center'  # Safe default — justification handled separately

        # Default: center (most common for comic/manga)
        return 'center'

    # -------------------------------------------------------------------
    # Padding
    # -------------------------------------------------------------------

    def _determine_padding(self, inp: BubbleLayoutInput) -> Insets:
        """Calculate proportional padding for layout box.

        Padding prevents text from touching bubble edges.
        Larger bubbles get more padding, but capped at reasonable max.
        """
        lw = inp.layout_box.width()
        lh = inp.layout_box.height()

        pad_x = max(self.MIN_PADDING, min(lw * self.PADDING_RATIO_X, self.MAX_PADDING_X))
        pad_y = max(self.MIN_PADDING, min(lh * self.PADDING_RATIO_Y, self.MAX_PADDING_Y))

        # Text-free bubbles may need asymmetric padding
        if inp.text_class == 'text_free':
            # Add extra padding on the side closer to bubble edge
            rel_x = (inp.layout_box.x() - inp.bubble_box.x()) / max(1, inp.bubble_box.width())
            if rel_x < 0.3:
                return Insets(
                    top=pad_y, right=pad_x, bottom=pad_y, left=pad_x * 0.5
                )
            elif rel_x > 0.7:
                return Insets(
                    top=pad_y, right=pad_x * 0.5, bottom=pad_y, left=pad_x
                )

        return Insets(
            top=pad_y,
            right=pad_x,
            bottom=pad_y,
            left=pad_x,
        )

    # -------------------------------------------------------------------
    # Margin
    # -------------------------------------------------------------------

    def _determine_margin(self, inp: BubbleLayoutInput) -> Insets:
        """Calculate margin (additional spacing beyond padding).

        Margin is used for special cases like SFX or multi-paragraph text.
        """
        mw = inp.layout_box.width()
        mh = inp.layout_box.height()

        margin = max(1.0, min(mw * self.MARGIN_RATIO, 4.0))

        if inp.text_class == 'sfx':
            return Insets(top=margin * 1.5, right=margin, bottom=margin * 1.5, left=margin)

        return Insets(top=margin, right=margin, bottom=margin, left=margin)

    # -------------------------------------------------------------------
    # Justification
    # -------------------------------------------------------------------

    def _determine_justification(
        self, inp: BubbleLayoutInput, alignment: str
    ) -> str:
        """Determine text justification.

        Justification stretches text to fill the line width.
        Used for long text in wide bubbles for cleaner appearance.
        """
        text = inp.text or ''

        # Short text: never justify
        if len(text) < 10:
            return 'none'

        # Center-aligned: no justification needed
        if alignment == 'center':
            return 'none'

        # Wide bubbles with long text: justify for clean edges
        aspect = inp.layout_box.width() / max(1, inp.layout_box.height())
        if aspect > 2.0 and len(text) > 40:
            return 'full'

        # Left/right aligned with medium text: consider distributed
        if alignment in ('left', 'right') and len(text) > 20:
            return 'none'  # Safe default

        return 'none'

    # -------------------------------------------------------------------
    # Anchor point
    # -------------------------------------------------------------------

    def _determine_anchor_point(
        self, inp: BubbleLayoutInput, plan: LayoutPlanDto
    ) -> Point:
        """Determine where text starts within layout box.

        Anchor point is relative to layout box (0,0 = top-left).
        Based on alignment and writing mode.
        """
        lw = inp.layout_box.width()
        lh = inp.layout_box.height()

        if plan.alignment == 'left':
            x = plan.padding.left
            y = plan.padding.top
        elif plan.alignment == 'right':
            x = lw - plan.padding.right
            y = plan.padding.top
        else:  # center
            x = lw / 2.0
            y = lh / 2.0

        if plan.writing_mode == 'vertical':
            # Vertical text starts from top-right (RTL) or top-left (LTR)
            if plan.text_direction == 'rtl':
                x = lw - plan.padding.right
            else:
                x = plan.padding.left
            y = plan.padding.top

        return Point(x=x, y=y)

    # -------------------------------------------------------------------
    # Confidence
    # -------------------------------------------------------------------

    def _calculate_confidence(self, inp: BubbleLayoutInput, plan: LayoutPlanDto) -> float:
        """Calculate confidence score for layout plan.

        Higher = more confident in the decisions made.
        """
        score = 0.5  # Base confidence

        # User override increases confidence
        if inp.user_alignment:
            score += 0.2

        # Clear shape signals increase confidence
        aspect = inp.layout_box.width() / max(1, inp.layout_box.height())
        if aspect > self.SHAPE_WIDE_THRESHOLD or aspect < self.SHAPE_TALL_THRESHOLD:
            score += 0.1

        # Page context increases confidence
        if inp.page_reading_order in ('ltr', 'rtl'):
            score += 0.1

        # Text presence increases confidence
        if inp.text and len(inp.text) > 5:
            score += 0.05

        return min(1.0, score)


# ---------------------------------------------------------------------------
# Convenience: convert TextBubble to BubbleLayoutInput
# ---------------------------------------------------------------------------

def bubble_to_layout_input(
    bubble,  # TextBubble or similar
    page_reading_order: str = 'ltr',
    page_writing_mode: str = 'horizontal',
) -> BubbleLayoutInput:
    """Convert a TextBubble to BubbleLayoutInput for layout planning."""
    box = bubble.box
    text_box = getattr(bubble, 'text_box', None) or box

    # layout_box: use text_box shrunk slightly, or box itself
    shrink = max(4, min(box.width(), box.height()) * 0.05)
    layout_box = QRectF(
        text_box.x() + shrink * 0.5,
        text_box.y() + shrink * 0.5,
        max(10, text_box.width() - shrink),
        max(10, text_box.height() - shrink),
    )
    return BubbleLayoutInput(
        bubble_box=box,
        layout_box=layout_box,
        text=getattr(bubble, 'translated', '') or getattr(bubble, 'text', '') or '',
        text_class=getattr(bubble, 'text_class', ''),
        page_reading_order=page_reading_order,
        page_writing_mode=page_writing_mode,
        user_alignment=getattr(bubble, 'alignment', None) or None,
        user_font_size=getattr(bubble, 'font_size', 0) or 0,
    )
