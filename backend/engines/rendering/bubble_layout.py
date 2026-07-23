from typing import Any

from ...core.models import TextBubble
from .renderer import font_pixel_size


def bubble_layout_cache_key(bubble: TextBubble) -> tuple:
    """Return the stable key shared by pipeline precomputation and API reads."""
    box = bubble.box
    text_box = bubble.text_box
    layout_box = bubble.layout_box
    return (
        bubble.id,
        round(box.x, 2),
        round(box.y, 2),
        round(box.width, 2),
        round(box.height, 2),
        tuple(round(value, 2) for value in bubble.source_xyxy()) if text_box is not None else None,
        (
            round(layout_box.x, 2),
            round(layout_box.y, 2),
            round(layout_box.width, 2),
            round(layout_box.height, 2),
        ) if layout_box is not None else None,
        bubble.text,
        bubble.translated,
        bubble.font_family,
        bubble.font_size,
        bubble.bold,
        bubble.italic,
        bubble.color,
        bubble.alignment,
        bubble.writing_mode,
        bubble.text_direction,
        bubble.justification,
        tuple(sorted(bubble.layout_padding.items())),
        tuple(sorted(bubble.layout_margin.items())),
        round(bubble.layout_confidence, 3),
        bubble.layout_reasoning,
    )


def compute_bubble_layout(bubble: TextBubble, image: Any, render_service: Any) -> dict:
    """Compute the serializable layout contract consumed by the desktop UI."""
    layout = render_service.get_layout_for_bubble(
        bubble.translated or bubble.text or "",
        bubble,
        image=image,
        font_family=bubble.font_family or None,
    )
    computed_font_family = layout.font.family() if hasattr(layout.font, "family") else ""
    font_mode = "fixed" if bubble.font_size > 0 else "auto"
    return {
        "font_mode": font_mode,
        "requested_font_size": bubble.font_size if font_mode == "fixed" else None,
        "font_size": font_pixel_size(layout.font),
        "font_family": computed_font_family,
        "overflow": bool(getattr(layout, "is_overflow", False)),
        "reached_min_font": bool(getattr(layout, "reached_min_font", False)),
        "line_height_ratio": float(getattr(layout, "line_height_ratio", 1.0)),
        "area_usage": float(getattr(layout, "area_usage", 0.0)),
        "diagnostics": dict(
            getattr(layout, "diagnostics", None) or {}
        ),
        "lines": [
            {
                "text": line.text,
                "x": line.x,
                "y": line.y,
                "width": line.width,
                "height": line.height,
                **(
                    {
                        "origin_x": line.origin_x,
                        "baseline_y": line.baseline_y,
                        "advance_width": line.advance_width,
                        "ink_left": line.ink_left,
                        "ink_top": line.ink_top,
                        "ink_width": line.ink_width,
                        "ink_height": line.ink_height,
                        "runs": [
                            {
                                "text": run.text,
                                "origin_x": run.origin_x,
                                "font_family": run.font_family,
                                "font_pixel_size": run.font_pixel_size,
                                "is_rtl": run.is_rtl,
                            }
                            for run in line.runs
                        ],
                    }
                    if getattr(line, "origin_x", None) is not None
                    else {}
                ),
            }
            for line in layout.line_layouts
        ],
    }
