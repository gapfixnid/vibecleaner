from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np

from .geometry import Rect


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
class AnchorPoint:
    """Mutable anchor point for text positioning within a layout box."""

    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}


@dataclass
class LayoutPlanDto:
    """Layout plan for a single bubble — produced by Layout Planner, consumed by Typesetter."""

    alignment: str = "center"  # 'left' | 'center' | 'right' | 'justify'
    padding: Insets = field(default_factory=Insets)
    margin: Insets = field(default_factory=Insets)
    writing_mode: str = "horizontal"  # 'horizontal' | 'vertical'
    justification: str = "none"  # 'none' | 'full' | 'distributed'
    anchor_point: AnchorPoint = field(default_factory=AnchorPoint)
    text_direction: str = "ltr"  # 'ltr' | 'rtl'
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "alignment": self.alignment,
            "padding": self.padding.to_dict(),
            "margin": self.margin.to_dict(),
            "writing_mode": self.writing_mode,
            "justification": self.justification,
            "anchor_point": self.anchor_point.to_dict(),
            "text_direction": self.text_direction,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class BubbleLayoutInput:
    """Input for layout planning — derived from BubbleData or TextBubble."""

    bubble_box: Rect  # Full bubble bounding box
    layout_box: Rect  # Area where text can be placed
    text: str = ""  # Text to render
    text_class: str = ""  # 'text_bubble' | 'text_free' | 'sfx'
    polygon: Optional[np.ndarray] = None  # Bubble polygon for shape analysis
    # Page-level context
    page_reading_order: str = "ltr"
    page_writing_mode: str = "horizontal"
    # User overrides
    user_alignment: Optional[str] = None
    user_font_size: int = 0