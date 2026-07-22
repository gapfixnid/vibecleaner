# engines/rendering/renderer.py
from dataclasses import dataclass
from typing import Callable, Optional as OptNone, Tuple

import numpy as np
from PySide6.QtGui import QFont, QFontMetricsF
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF, Qt
from .typesetting import dp_wrap_text, fit_font_size, unicode_break_tokens
from ...infrastructure.fonts import resolver as font_resolver
import logging

logger = logging.getLogger(__name__)

_LINE_START_PUNCTUATION = set(",.!?;:)]}〉》」』】〕〉！？。，、：；》」』】")
_LINE_END_PUNCTUATION = set("([{〈《「『【〔")


def font_pixel_size(font: QFont) -> int:
    """Return the effective font size in pixels for every render boundary."""
    pixel_size = getattr(font, "pixelSize", lambda: -1)()
    if pixel_size is not None and int(pixel_size) > 0:
        return int(pixel_size)
    point_size = getattr(font, "pointSizeF", lambda: -1.0)()
    return max(1, int(round(float(point_size) * 96.0 / 72.0)))


def _set_font_pixel_size(font: QFont, size: float) -> None:
    font.setPixelSize(max(1, int(round(size))))


@dataclass
class TextLineLayout:
    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class TextLayoutResult:
    font: QFont
    lines: list[str]
    render_width: float
    line_layouts: list[TextLineLayout]
    score: float = 0.0
    is_overflow: bool = False
    reached_min_font: bool = False
    line_height_ratio: float = 1.0
    area_usage: float = 0.0


class TextRenderer:
    # Automatic layouts should remain readable even when a translation is
    # longer than the source text. A manually selected font size can still be
    # smaller; this floor applies only while choosing an automatic size.
    AUTO_READABILITY_MIN_FONT_SIZE = 11.0

    def __init__(self, min_font_size: float = 6.0, max_font_size: float = 48.0):
        self.min_font_size = float(min_font_size)
        self.max_font_size = float(max_font_size)

    @staticmethod
    def _inset_value(insets: dict[str, float] | None, side: str) -> float:
        if not insets:
            return 0.0
        try:
            return max(0.0, float(insets.get(side, 0.0) or 0.0))
        except (TypeError, ValueError):
            return 0.0

    def content_rect(
        self,
        rect: QRectF,
        padding: dict[str, float] | None = None,
        margin: dict[str, float] | None = None,
    ) -> QRectF:
        """Return the rectangular text area after planned insets."""
        explicit_insets = any(
            self._inset_value(source, side) > 0
            for source in (padding, margin)
            for side in ("top", "right", "bottom", "left")
        )
        if explicit_insets:
            left = self._inset_value(padding, "left") + self._inset_value(margin, "left")
            right = self._inset_value(padding, "right") + self._inset_value(margin, "right")
            top = self._inset_value(padding, "top") + self._inset_value(margin, "top")
            bottom = self._inset_value(padding, "bottom") + self._inset_value(margin, "bottom")
        else:
            left = right = min(8.0, rect.width() * 0.08)
            top = bottom = min(6.0, rect.height() * 0.08)

        max_horizontal = max(0.0, rect.width() - 10.0)
        max_vertical = max(0.0, rect.height() - 10.0)
        horizontal = left + right
        vertical = top + bottom
        if horizontal > max_horizontal and horizontal > 0:
            scale = max_horizontal / horizontal
            left *= scale
            right *= scale
        if vertical > max_vertical and vertical > 0:
            scale = max_vertical / vertical
            top *= scale
            bottom *= scale

        return QRectF(
            rect.x() + left,
            rect.y() + top,
            max(1.0, rect.width() - left - right),
            max(1.0, rect.height() - top - bottom),
        )

    def make_safe_mask(
        self,
        mask: np.ndarray,
        padding: dict[str, float] | None = None,
        margin: dict[str, float] | None = None,
        stroke_width: float = 1.0,
        inset_scale: float = 1.0,
    ) -> np.ndarray:
        """Build a boundary-distance safe area from a bubble mask."""
        import cv2

        mask_bool = np.asarray(mask) > 0
        if mask_bool.ndim != 2 or not bool(mask_bool.any()):
            return np.zeros_like(mask_bool, dtype=bool)

        totals = {
            side: (
                self._inset_value(padding, side)
                + self._inset_value(margin, side)
            ) * max(0.0, float(inset_scale))
            for side in ("top", "right", "bottom", "left")
        }
        if any(value > 0 for value in totals.values()):
            boundary_clearance = max(
                float(stroke_width),
                min(totals.values()) + float(stroke_width),
            )
        else:
            default_padding = max(2.0, min(mask_bool.shape) * 0.03)
            boundary_clearance = default_padding + float(stroke_width)

        distance = cv2.distanceTransform(mask_bool.astype(np.uint8), cv2.DIST_L2, 5)
        safe = distance >= boundary_clearance

        # Distance transform supplies the minimum boundary clearance. Apply
        # directional clearances relative to the mask bounding box as well.
        mask_ys, mask_xs = np.where(mask_bool)
        y_min = int(mask_ys.min())
        y_max = int(mask_ys.max()) + 1
        x_min = int(mask_xs.min())
        x_max = int(mask_xs.max()) + 1
        directional_clearance = {
            side: max(0, int(round(value + float(stroke_width))))
            for side, value in totals.items()
        }
        if directional_clearance["top"]:
            safe[: min(y_max, y_min + directional_clearance["top"]), :] = False
        if directional_clearance["bottom"]:
            safe[max(y_min, y_max - directional_clearance["bottom"]):, :] = False
        if directional_clearance["left"]:
            safe[:, : min(x_max, x_min + directional_clearance["left"])] = False
        if directional_clearance["right"]:
            safe[:, max(x_min, x_max - directional_clearance["right"]):] = False
        return safe

    def _automatic_min_font_size(self, min_size: float, max_size: float) -> float:
        return min(max_size, max(min_size, self.AUTO_READABILITY_MIN_FONT_SIZE))
        
    def wrap_text(self, text: str, width: float, font: QFont, allow_char_break: bool = False) -> list[str] | None:
        """Wrap text using DP for optimal line breaking; falls back to greedy."""
        metrics = QFontMetricsF(font)
        measure = lambda s: metrics.horizontalAdvance(s)
        line_height = metrics.lineSpacing()
        result = dp_wrap_text(text, measure, width, float('inf'), no_space=False, line_height=line_height)
        if all(metrics.horizontalAdvance(l) <= width * 1.01 for l in result.lines):
            return result.lines
        return self._wrap_text_greedy(text, width, font, allow_char_break)

    def _wrap_text_greedy(self, text: str, width: float, font: QFont, allow_char_break: bool = False) -> list[str] | None:
        """Original greedy wrapping (backward compatibility fallback)."""
        metrics = QFontMetricsF(font)
        paragraphs = text.split('\n')
        all_lines = []
        for paragraph in paragraphs:
            if not paragraph.strip():
                all_lines.append("")
                continue
            words = paragraph.split(' ')
            current_line = ""
            for word in words:
                if not word:
                    continue
                test_line = word if not current_line else current_line + " " + word
                if metrics.horizontalAdvance(test_line) <= width:
                    current_line = test_line
                else:
                    if current_line:
                        all_lines.append(current_line)
                        current_line = ""
                        if metrics.horizontalAdvance(word) <= width:
                            current_line = word
                            continue
                    if allow_char_break:
                        char_line = ""
                        for char in word:
                            test_char = char_line + char
                            if metrics.horizontalAdvance(test_char) <= width:
                                char_line = test_char
                            else:
                                if char_line:
                                    all_lines.append(char_line)
                                char_line = char
                        current_line = char_line
                    else:
                        return None
            if current_line:
                all_lines.append(current_line)
        return all_lines

    def wrap_korean_text(self, text: str, width: float, font: QFont, allow_char_break: bool = True) -> list[str] | None:
        """Wrap Korean/CJK text using DP for optimal line breaking."""
        metrics = QFontMetricsF(font)
        measure = lambda s: metrics.horizontalAdvance(s)
        line_height = metrics.lineSpacing()
        result = dp_wrap_text(text, measure, width, float('inf'), no_space=True, line_height=line_height)
        if all(metrics.horizontalAdvance(l) <= width * 1.01 for l in result.lines):
            return result.lines
        return self._wrap_korean_text_greedy(text, width, font, allow_char_break)

    def _wrap_korean_text_greedy(self, text: str, width: float, font: QFont, allow_char_break: bool = True) -> list[str] | None:
        """Original greedy Korean wrapping (backward compatibility fallback)."""
        metrics = QFontMetricsF(font)
        paragraphs = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        wrapped = []
        for paragraph in paragraphs:
            if not paragraph.strip():
                wrapped.append("")
                continue
            words = paragraph.split(" ")
            current = ""
            for word in words:
                if not word:
                    continue
                candidate = word if not current else f"{current} {word}"
                if metrics.horizontalAdvance(candidate) <= width:
                    current = candidate
                    continue
                if current:
                    wrapped.append(current)
                    current = ""
                if metrics.horizontalAdvance(word) <= width:
                    current = word
                    continue
                if not allow_char_break:
                    return None
                parts = self._split_long_korean_word(word, width, metrics)
                if not parts:
                    return None
                wrapped.extend(parts[:-1])
                current = parts[-1]
            if current:
                wrapped.append(current)
        return wrapped

    def _split_long_korean_word(self, word: str, width: float, metrics: QFontMetricsF) -> list[str]:
        break_after = set(",.!?;:)]}…")
        break_before = set("([{")
        parts: list[str] = []
        current = ""
        for char in word:
            candidate = current + char
            if not current or metrics.horizontalAdvance(candidate) <= width:
                current = candidate
                continue
            if current[-1:] in break_before and len(current) > 1:
                parts.append(current[:-1])
                current = current[-1] + char
            else:
                parts.append(current)
                current = char
        if current:
            parts.append(current)
        merged: list[str] = []
        for part in parts:
            if merged and part and part[0] in break_after:
                merged[-1] += part[0]
                if len(part) > 1:
                    merged.append(part[1:])
            else:
                merged.append(part)
        return [part for part in merged if part]

    def find_optimal_font_size(
        self,
        text: str,
        rect: QRectF,
        font_family: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        padding: dict[str, float] | None = None,
        margin: dict[str, float] | None = None,
    ) -> tuple[QFont, list[str], float]:
        """
        Employs binary search to find the maximum font size that fits the text inside rect.
        Includes safety margins and dynamic capping for aesthetically pleasing results.
        """
        # Calculate dynamic safety margin padding (proportional to bubble size)
        if font_family is None:
            # Use font resolver for best available font
            resolved_font, chain = font_resolver.resolve(text, target_lang="Korean")
            font_family = resolved_font.name
            logger.debug(f"Font resolved: {font_family} (chain: {' → '.join(chain)})")
        else:
            app = QApplication.instance()
            if app is None or not app.font().family():
                font_family = "Segoe UI"
        max_size = float(self.max_font_size if max_size is None else max_size)
        configured_min_size = float(self.min_font_size if min_size is None else min_size)
        min_size = self._automatic_min_font_size(configured_min_size, max_size)

        content_rect = self.content_rect(rect, padding=padding, margin=margin)
        width = max(1.0, content_rect.width())
        height = max(1.0, content_rect.height())
        
        # We first try to find a font size where words do not need to be broken (allow_char_break=False)
        low = min_size
        dynamic_max = min(max_size, height * 0.70, width * 0.70)
        high = max(min_size, dynamic_max)
        
        optimal_size = min_size
        optimal_lines = None
        
        # Binary search without character breaking
        for _ in range(8):
            mid = (low + high) / 2.0
            font = QFont(font_family)
            _set_font_pixel_size(font, mid)
            
            lines = self.wrap_korean_text(text, width, font, allow_char_break=False)
            if lines is None:
                fits = False
            else:
                metrics = QFontMetricsF(font)
                line_height = metrics.height()
                total_height = line_height * len(lines)
                
                fits = True
                if total_height > height:
                    fits = False
                else:
                    for line in lines:
                        if metrics.horizontalAdvance(line) > width:
                            fits = False
                            break
            
            if fits:
                optimal_size = mid
                optimal_lines = lines
                low = mid + 0.1
            else:
                high = mid - 0.1
                
        # If we couldn't fit the text without character breaking, fall back to allow character breaking
        if optimal_lines is None:
            low = min_size
            high = max(min_size, dynamic_max)
            optimal_size = min_size
            optimal_lines = self.wrap_korean_text(text, width, QFont(font_family, int(min_size)), allow_char_break=True)
            
            for _ in range(8):
                mid = (low + high) / 2.0
                font = QFont(font_family)
                _set_font_pixel_size(font, mid)
                
                lines = self.wrap_korean_text(text, width, font, allow_char_break=True)
                metrics = QFontMetricsF(font)
                line_height = metrics.height()
                total_height = line_height * len(lines)
                
                fits = True
                if total_height > height:
                    fits = False
                else:
                    for line in lines:
                        if metrics.horizontalAdvance(line) > width:
                            fits = False
                            break
                            
                if fits:
                    optimal_size = mid
                    optimal_lines = lines
                    low = mid + 0.1
                else:
                    high = mid - 0.1
                    
        final_font = QFont(font_family)
        _set_font_pixel_size(final_font, optimal_size)
        return final_font, optimal_lines or [text], width

    def layout_lines_in_rect(
        self,
        lines: list[str],
        rect: QRectF,
        font: QFont,
        render_width: float,
        alignment: str = 'center',
        min_size: float | None = None,
        line_height_ratio: float = 1.0,
    ) -> TextLayoutResult:
        min_size = float(self.min_font_size if min_size is None else min_size)
        metrics = QFontMetricsF(font)
        glyph_height = metrics.height()
        line_height = max(glyph_height, glyph_height * line_height_ratio)
        total_height = line_height * len(lines)
        y_offset = max(0.0, (rect.height() - total_height) / 2.0)

        # Horizontal positioning based on alignment
        if alignment == 'left':
            x_pos = rect.x()
        elif alignment == 'right':
            x_pos = rect.x() + rect.width() - render_width
        else:  # center (default)
            x_pos = rect.x() + (rect.width() - render_width) / 2.0

        line_layouts = [
            TextLineLayout(
                text=line,
                x=x_pos,
                y=rect.y() + y_offset + index * line_height,
                width=render_width,
                height=line_height,
            )
            for index, line in enumerate(lines)
        ]
        is_overflow = total_height > rect.height() or any(metrics.horizontalAdvance(line) > render_width for line in lines)
        text_area = sum(max(1.0, metrics.horizontalAdvance(line)) * glyph_height * 0.72 for line in lines)
        available_area = max(1.0, rect.width() * rect.height())
        return TextLayoutResult(
            font=font,
            lines=lines,
            render_width=render_width,
            line_layouts=line_layouts,
            is_overflow=is_overflow,
            reached_min_font=font_pixel_size(font) <= int(round(min_size)),
            line_height_ratio=line_height_ratio,
            area_usage=min(1.0, text_area / available_area),
        )

    def find_optimal_layout_in_rect(
        self,
        text: str,
        rect: QRectF,
        font_family: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        alignment: str = "center",
        padding: dict[str, float] | None = None,
        margin: dict[str, float] | None = None,
    ) -> TextLayoutResult:
        """Choose rectangle font size, wrapping, and line spacing together."""
        if font_family is None:
            resolved_font, chain = font_resolver.resolve(text, target_lang="Korean")
            font_family = resolved_font.name
            logger.debug(f"Font resolved (rect): {font_family} (chain: {' → '.join(chain)})")
        else:
            app = QApplication.instance()
            if app is None or not app.font().family():
                font_family = "Segoe UI"

        max_size = float(self.max_font_size if max_size is None else max_size)
        configured_min = float(self.min_font_size if min_size is None else min_size)
        minimum = self._automatic_min_font_size(configured_min, max_size)
        content_rect = self.content_rect(rect, padding=padding, margin=margin)
        dynamic_max = max(
            minimum,
            min(max_size, content_rect.height() * 0.70, content_rect.width() * 0.70),
        )
        candidate_sizes = self._candidate_font_sizes(minimum, dynamic_max)

        for allow_char_break in (False, True):
            best_layout = self._best_rect_layout_for_candidates(
                text,
                content_rect,
                font_family,
                candidate_sizes,
                alignment,
                minimum,
                allow_char_break,
            )
            if best_layout is not None:
                return best_layout

        font = QFont(font_family)
        _set_font_pixel_size(font, minimum)
        lines = self.wrap_korean_text(
            text,
            content_rect.width(),
            font,
            allow_char_break=True,
        ) or [text]
        fallback = self.layout_lines_in_rect(
            lines,
            content_rect,
            font,
            content_rect.width(),
            alignment=alignment,
            min_size=minimum,
            line_height_ratio=1.0,
        )
        fallback.is_overflow = True
        return fallback

    def _best_rect_layout_for_candidates(
        self,
        text: str,
        rect: QRectF,
        font_family: str,
        candidate_sizes: list[float],
        alignment: str,
        min_size: float,
        allow_char_break: bool,
    ) -> TextLayoutResult | None:
        best_layout = None
        best_key = None
        preferred_max_lines = 3 if rect.width() > rect.height() * 1.6 else 4

        for size in candidate_sizes:
            font = QFont(font_family)
            _set_font_pixel_size(font, size)
            lines = self.wrap_korean_text(
                text,
                rect.width(),
                font,
                allow_char_break=allow_char_break,
            )
            if lines is None:
                continue
            metrics = QFontMetricsF(font)
            advances = [float(metrics.horizontalAdvance(line)) for line in lines]
            for line_height_ratio in (1.12, 1.06, 1.0, 1.18):
                layout = self.layout_lines_in_rect(
                    lines,
                    rect,
                    font,
                    rect.width(),
                    alignment=alignment,
                    min_size=min_size,
                    line_height_ratio=line_height_ratio,
                )
                if layout.is_overflow:
                    continue
                utilization = [advance / max(1.0, rect.width()) for advance in advances]
                balance = float(np.std(utilization)) if len(utilization) > 1 else 0.0
                key = (
                    self._bad_line_break_count(lines, text),
                    max(0, len(lines) - preferred_max_lines),
                    -font_pixel_size(font),
                    balance,
                    abs(layout.area_usage - 0.62),
                    abs(line_height_ratio - 1.12),
                )
                if best_key is None or key < best_key:
                    best_key = key
                    best_layout = layout
        return best_layout

    def layout_text_at_fixed_size(
        self,
        text: str,
        rect: QRectF,
        font_size: float,
        mask: np.ndarray | None = None,
        font_family: str | None = None,
        alignment: str = "center",
        padding: dict[str, float] | None = None,
        margin: dict[str, float] | None = None,
        target_center_y: float | None = None,
    ) -> TextLayoutResult:
        """Lay out text without changing the caller's requested font size."""
        if font_family is None:
            resolved_font, chain = font_resolver.resolve(text, target_lang="Korean")
            font_family = resolved_font.name
            logger.debug(f"Font resolved (fixed): {font_family} (chain: {' → '.join(chain)})")
        else:
            app = QApplication.instance()
            if app is None or not app.font().family():
                font_family = "Segoe UI"

        requested_size = max(1.0, float(font_size))
        font = QFont(font_family)
        _set_font_pixel_size(font, requested_size)

        if mask is not None:
            candidate_masks = [
                self.make_safe_mask(
                    mask,
                    padding=padding,
                    margin=margin,
                    stroke_width=max(1.0, requested_size / 12.0),
                    inset_scale=scale,
                )
                for scale in (1.0, 0.7)
            ]

            for candidate_mask in candidate_masks:
                if candidate_mask.ndim != 2 or not bool(candidate_mask.any()):
                    continue
                for allow_char_break in (False, True):
                    layout = self._best_layout_for_font_candidates(
                        text,
                        rect,
                        candidate_mask,
                        font_family,
                        [requested_size],
                        allow_char_break=allow_char_break,
                        dynamic_max=requested_size,
                        min_size=0.0,
                        target_center_y=target_center_y,
                    )
                    if layout is not None:
                        layout.reached_min_font = False
                        return layout

            # Preserve the requested size even when the shape-aware layout
            # cannot fit. A rectangular fallback still gives the UI useful
            # line positions while the overflow flag remains authoritative.
            fallback = self.layout_text_at_fixed_size(
                text,
                rect,
                requested_size,
                font_family=font_family,
                alignment=alignment,
                padding=padding,
                margin=margin,
                target_center_y=target_center_y,
            )
            fallback.is_overflow = True
            return fallback

        inner_rect = self.content_rect(rect, padding=padding, margin=margin)
        for allow_char_break in (False, True):
            layout = self._best_rect_layout_for_candidates(
                text,
                inner_rect,
                font_family,
                [requested_size],
                alignment,
                0.0,
                allow_char_break,
            )
            if layout is not None:
                layout.reached_min_font = False
                return layout

        lines = self.wrap_korean_text(
            text,
            inner_rect.width(),
            font,
            allow_char_break=True,
        ) or [text]
        fallback = self.layout_lines_in_rect(
            lines,
            inner_rect,
            font,
            inner_rect.width(),
            alignment=alignment,
            min_size=0.0,
            line_height_ratio=1.0,
        )
        fallback.is_overflow = True
        fallback.reached_min_font = False
        return fallback

    def center_layout_vertically(
        self,
        layout: TextLayoutResult,
        target_center_y: float,
        bounds: QRectF,
    ) -> TextLayoutResult:
        """Move an existing line block vertically without changing its typesetting."""
        if not layout.line_layouts:
            return layout

        block_top = min(line.y for line in layout.line_layouts)
        block_bottom = max(line.y + line.height for line in layout.line_layouts)
        block_center = (block_top + block_bottom) / 2.0
        desired_shift = float(target_center_y) - block_center
        min_shift = bounds.top() - block_top
        max_shift = bounds.bottom() - block_bottom
        shift = max(min_shift, min(max_shift, desired_shift))

        if abs(shift) < 0.01:
            return layout

        return TextLayoutResult(
            font=layout.font,
            lines=list(layout.lines),
            render_width=layout.render_width,
            line_layouts=[
                TextLineLayout(
                    text=line.text,
                    x=line.x,
                    y=line.y + shift,
                    width=line.width,
                    height=line.height,
                )
                for line in layout.line_layouts
            ],
            score=layout.score,
            is_overflow=layout.is_overflow,
            reached_min_font=layout.reached_min_font,
            line_height_ratio=layout.line_height_ratio,
            area_usage=layout.area_usage,
        )

    def make_ellipse_mask(self, width: int, height: int, inset: int = 0) -> np.ndarray:
        width = max(1, int(width))
        height = max(1, int(height))
        inset = max(0, int(inset))
        usable_w = max(1.0, width - inset * 2)
        usable_h = max(1.0, height - inset * 2)
        cy_grid, cx_grid = np.ogrid[:height, :width]
        cx = (width - 1) / 2.0
        cy = (height - 1) / 2.0
        rx = max(1.0, usable_w / 2.0)
        ry = max(1.0, usable_h / 2.0)
        return ((((cx_grid - cx) / rx) ** 2 + ((cy_grid - cy) / ry) ** 2) <= 1.0).astype(np.uint8)

    def find_optimal_font_size_for_mask(
        self,
        text: str,
        rect: QRectF,
        mask: np.ndarray,
        font_family: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        padding: dict[str, float] | None = None,
        margin: dict[str, float] | None = None,
        target_center_y: float | None = None,
    ) -> TextLayoutResult:
        if font_family is None:
            resolved_font, chain = font_resolver.resolve(text, target_lang="Korean")
            font_family = resolved_font.name
            logger.debug(f"Font resolved (mask): {font_family} (chain: {' → '.join(chain)})")
        max_size = float(self.max_font_size if max_size is None else max_size)
        configured_min_size = float(self.min_font_size if min_size is None else min_size)
        min_size = self._automatic_min_font_size(configured_min_size, max_size)

        mask_bool = np.asarray(mask) > 0
        if mask_bool.ndim != 2 or not bool(mask_bool.any()):
            font, lines, render_width = self.find_optimal_font_size(
                text,
                rect,
                font_family,
                min_size,
                max_size,
                padding=padding,
                margin=margin,
            )
            content_rect = self.content_rect(rect, padding=padding, margin=margin)
            return self.layout_lines_in_rect(lines, content_rect, font, render_width, min_size=min_size)

        dynamic_max = min(max_size, max(min_size, rect.height() * 0.85, rect.width() * 0.65))
        candidate_sizes = self._candidate_font_sizes(min_size, dynamic_max)
        safe_masks = [
            self.make_safe_mask(
                mask_bool,
                padding=padding,
                margin=margin,
                stroke_width=max(1.0, dynamic_max / 12.0),
                inset_scale=scale,
            )
            for scale in (1.0, 0.7)
        ]
        best_layout = None
        for safe_mask in safe_masks:
            best_layout = self._best_layout_for_font_candidates(
                text,
                rect,
                safe_mask,
                font_family,
                candidate_sizes,
                allow_char_break=False,
                dynamic_max=dynamic_max,
                min_size=min_size,
                target_center_y=target_center_y,
            )
            if best_layout is not None:
                return best_layout

        for safe_mask in safe_masks:
            best_layout = self._best_layout_for_font_candidates(
                text,
                rect,
                safe_mask,
                font_family,
                candidate_sizes,
                allow_char_break=True,
                dynamic_max=dynamic_max,
                min_size=min_size,
                target_center_y=target_center_y,
            )
            if best_layout is not None:
                return best_layout

        font, lines, render_width = self.find_optimal_font_size(
            text,
            rect,
            font_family,
            min_size,
            max_size,
            padding=padding,
            margin=margin,
        )
        content_rect = self.content_rect(rect, padding=padding, margin=margin)
        fallback = self.layout_lines_in_rect(
            lines,
            content_rect,
            font,
            render_width,
            min_size=min_size,
        )
        fallback.is_overflow = True
        return fallback

    def _candidate_font_sizes(self, min_size: float, max_size: float) -> list[float]:
        if max_size <= min_size:
            return [min_size]
        values = np.linspace(max_size, min_size, num=18)
        rounded = []
        for value in values:
            size = round(float(value) * 2.0) / 2.0
            if size not in rounded:
                rounded.append(size)
        if min_size not in rounded:
            rounded.append(min_size)
        return rounded

    def _best_layout_for_font_candidates(
        self,
        text: str,
        rect: QRectF,
        mask: np.ndarray,
        font_family: str,
        candidate_sizes: list[float],
        allow_char_break: bool,
        dynamic_max: float,
        min_size: float,
        target_center_y: float | None = None,
    ) -> TextLayoutResult | None:
        best_layout = None
        best_key = None
        if rect.width() > rect.height() * 1.6:
            preferred_max_lines = 3
        elif rect.height() > rect.width() * 1.6:
            preferred_max_lines = 6
        else:
            preferred_max_lines = 4

        for size in candidate_sizes:
            font = QFont(font_family)
            _set_font_pixel_size(font, size)
            for line_height_ratio in (1.12, 1.06, 1.0, 1.18):
                layout = self._layout_text_in_mask(
                    text,
                    rect,
                    mask,
                    font,
                    allow_char_break=allow_char_break,
                    min_size=min_size,
                    line_height_ratio=line_height_ratio,
                    target_center_y=target_center_y,
                )
                if layout is None:
                    continue

                bad_breaks = self._bad_line_break_count(layout.lines, text)
                excess_lines = max(0, len(layout.lines) - preferred_max_lines)
                key = (
                    bad_breaks,
                    excess_lines,
                    -font_pixel_size(layout.font),
                    layout.score,
                    abs(line_height_ratio - 1.12),
                )
                if best_key is None or key < best_key:
                    best_key = key
                    best_layout = layout

        return best_layout

    def _bad_line_break_count(self, lines: list[str], text: str) -> int:
        if len(text.strip()) <= 1:
            return 0
        bad = 0
        for line in lines:
            stripped = line.strip()
            if len(stripped) <= 1:
                bad += 1
            if stripped[:1] in _LINE_START_PUNCTUATION:
                bad += 1
            if stripped[-1:] in _LINE_END_PUNCTUATION:
                bad += 1
        return bad

    def _layout_text_in_mask(
        self,
        text: str,
        rect: QRectF,
        mask: np.ndarray,
        font: QFont,
        allow_char_break: bool,
        min_size: float,
        line_height_ratio: float = 1.0,
        target_center_y: float | None = None,
    ) -> TextLayoutResult | None:
        metrics = QFontMetricsF(font)
        glyph_height = max(1.0, metrics.height())
        line_height = max(glyph_height, glyph_height * line_height_ratio)
        slots = self._line_slots_from_mask(mask, rect, glyph_height, line_height)
        if not slots:
            return None

        best_result = None
        best_score = float("inf")

        for start in range(len(slots)):
            available_slots = slots[start:]
            wrap_result = self._best_wrap_text_to_slots(text, available_slots, font, allow_char_break)
            if wrap_result is None:
                continue

            wrapped, advances, wrap_score = wrap_result
            used_slots = available_slots[: len(wrapped)]
            line_layouts = [
                TextLineLayout(
                    text=line,
                    x=slot.x,
                    y=slot.y,
                    width=slot.width,
                    height=slot.height,
                )
                for line, slot in zip(wrapped, used_slots)
            ]

            score = self._layout_score(
                line_layouts,
                advances,
                used_slots,
                rect,
                mask,
                line_height,
                wrap_score,
                target_center_y=target_center_y,
            )
            if score < best_score:
                best_score = score
                text_area = sum(max(1.0, advance) * glyph_height * 0.72 for advance in advances)
                safe_area = float(max(1, np.count_nonzero(mask)))
                best_result = TextLayoutResult(
                    font=font,
                    lines=wrapped,
                    render_width=max(slot.width for slot in used_slots),
                    line_layouts=line_layouts,
                    score=score,
                    is_overflow=False,
                    reached_min_font=font_pixel_size(font) <= int(round(min_size)),
                    line_height_ratio=line_height_ratio,
                    area_usage=min(1.0, text_area / safe_area),
                )

        return best_result

    def _layout_score(
        self,
        line_layouts: list[TextLineLayout],
        advances: list[float],
        slots: list[TextLineLayout],
        rect: QRectF,
        mask: np.ndarray,
        line_height: float,
        wrap_score: float,
        target_center_y: float | None = None,
    ) -> float:
        if not line_layouts:
            return float("inf")

        used_center = (line_layouts[0].y + line_layouts[-1].y + line_height) / 2.0
        mask_ys = np.where(mask)[0]
        mask_center = (
            rect.y() + float(np.mean(mask_ys))
            if mask_ys.size
            else rect.y() + rect.height() / 2.0
        )
        desired_center = mask_center if target_center_y is None else float(target_center_y)
        center_penalty = abs(used_center - desired_center) / max(1.0, rect.height())
        vertical_fill = (len(line_layouts) * line_height) / max(1.0, rect.height())
        avg_util = float(
            np.mean([advance / max(1.0, slot.width) for advance, slot in zip(advances, slots)])
        )
        text_area = sum(max(1.0, advance) * line_height * 0.72 for advance in advances)
        bubble_area = float(max(1, np.count_nonzero(mask)))
        fill_ratio = text_area / bubble_area
        target_fill = 0.62
        fill_penalty = max(0.0, target_fill - fill_ratio) ** 2 * 2.8
        overfill_penalty = max(0.0, fill_ratio - 0.84) ** 2 * 1.5
        underfill_penalty = max(0.0, 0.36 - vertical_fill) * 0.4
        return (
            wrap_score
            + center_penalty * 0.9
            + underfill_penalty
            + fill_penalty
            + overfill_penalty
            - avg_util * 0.10
        )

    def _line_slots_from_mask(
        self,
        mask: np.ndarray,
        rect: QRectF,
        glyph_height: float,
        line_advance: float | None = None,
    ) -> list[TextLineLayout]:
        ys, _ = np.where(mask)
        if ys.size == 0:
            return []

        y_min = int(ys.min())
        y_max = int(ys.max()) + 1
        band_height = max(1, int(np.ceil(glyph_height)))
        line_advance = max(glyph_height, float(line_advance or glyph_height))
        advance_pixels = max(1, int(round(line_advance)))
        min_width = max(10.0, rect.width() * 0.12)
        slots: list[TextLineLayout] = []
        mask_xs = np.where(mask)[1]
        mask_center_x = float(np.mean(mask_xs)) if mask_xs.size else mask.shape[1] / 2.0

        top = y_min
        while top + band_height <= y_max:
            band = np.asarray(mask[top : top + band_height, :], dtype=bool)
            if band.shape[0] == band_height and bool(np.all(np.any(band, axis=1))):
                common = np.all(band, axis=0).astype(np.int8)
                changes = np.diff(np.pad(common, (1, 1)))
                starts = np.where(changes == 1)[0]
                ends = np.where(changes == -1)[0]
                runs = [
                    (int(start), int(end))
                    for start, end in zip(starts, ends)
                    if end - start >= min_width
                ]
                if runs:
                    x1, x2 = max(
                        runs,
                        key=lambda run: (
                            run[1] - run[0],
                            -abs((run[0] + run[1]) / 2.0 - mask_center_x),
                        ),
                    )
                    slots.append(
                        TextLineLayout(
                            text="",
                            x=rect.x() + x1,
                            y=rect.y() + top,
                            width=float(x2 - x1),
                            height=line_advance,
                        )
                    )

            top += advance_pixels

        return slots

    def _best_wrap_text_to_slots(
        self,
        text: str,
        slots: list[TextLineLayout],
        font: QFont,
        allow_char_break: bool,
    ) -> tuple[list[str], list[float], float] | None:
        paragraphs = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lines: list[str] = []
        advances: list[float] = []
        total_score = 0.0
        slot_offset = 0

        for index, paragraph in enumerate(paragraphs):
            remaining = paragraphs[index + 1 :]
            min_remaining_slots = sum(1 for item in remaining if item.strip()) + sum(1 for item in remaining if not item.strip())
            max_end = max(slot_offset, len(slots) - min_remaining_slots)

            if not paragraph.strip():
                if slot_offset >= len(slots):
                    return None
                lines.append("")
                advances.append(0.0)
                slot_offset += 1
                continue

            paragraph_slots = slots[slot_offset:max_end]
            result = self._best_wrap_paragraph_to_slots(paragraph, paragraph_slots, font, allow_char_break)
            if result is None:
                return None

            paragraph_lines, paragraph_advances, paragraph_score = result
            lines.extend(paragraph_lines)
            advances.extend(paragraph_advances)
            total_score += paragraph_score
            slot_offset += len(paragraph_lines)

        if not lines:
            return None
        return lines, advances, total_score

    def _best_wrap_paragraph_to_slots(
        self,
        paragraph: str,
        slots: list[TextLineLayout],
        font: QFont,
        allow_char_break: bool,
    ) -> tuple[list[str], list[float], float] | None:
        if not slots:
            return None

        candidates = []
        primary_tokens = unicode_break_tokens(paragraph)
        if primary_tokens:
            candidates.append((primary_tokens, ""))
        if allow_char_break:
            grapheme_tokens = unicode_break_tokens(paragraph, allow_grapheme_breaks=True)
            if grapheme_tokens and grapheme_tokens != primary_tokens:
                candidates.append((grapheme_tokens, ""))

        metrics = QFontMetricsF(font)
        best = None

        for tokens, joiner in candidates:
            result = self._wrap_tokens_with_dp(tokens, joiner, slots, metrics)
            if result is None:
                continue
            if best is None or result[2] < best[2]:
                best = result

        return best

    def _wrap_tokens_with_dp(
        self,
        tokens: list[str],
        joiner: str,
        slots: list[TextLineLayout],
        metrics: QFontMetricsF,
    ) -> tuple[list[str], list[float], float] | None:
        line_cache: dict[tuple[int, int], tuple[str, float]] = {}
        memo: dict[tuple[int, int], tuple[float, list[str], list[float]] | None] = {}

        def line_info(start: int, end: int) -> tuple[str, float]:
            key = (start, end)
            if key not in line_cache:
                line = joiner.join(tokens[start:end])
                line_cache[key] = (line, float(metrics.horizontalAdvance(line)))
            return line_cache[key]

        def solve(token_index: int, slot_index: int) -> tuple[float, list[str], list[float]] | None:
            if token_index >= len(tokens):
                return 0.0, [], []
            if slot_index >= len(slots):
                return None

            key = (token_index, slot_index)
            if key in memo:
                return memo[key]

            slot_width = slots[slot_index].width
            best_state = None

            for end in range(token_index + 1, len(tokens) + 1):
                line, advance = line_info(token_index, end)
                if advance > slot_width:
                    break

                rest = solve(end, slot_index + 1)
                if rest is None:
                    continue

                is_last_line = end >= len(tokens)
                line_score = self._line_wrap_score(line, advance, slot_width, is_last_line)
                rest_score, rest_lines, rest_advances = rest
                score = line_score + rest_score
                candidate = (score, [line] + rest_lines, [advance] + rest_advances)
                if best_state is None or score < best_state[0]:
                    best_state = candidate

            memo[key] = best_state
            return best_state

        result = solve(0, 0)
        if result is None:
            return None
        score, lines, advances = result
        return lines, advances, score

    def _line_wrap_score(self, line: str, advance: float, width: float, is_last_line: bool) -> float:
        width = max(1.0, width)
        util = max(0.0, min(1.0, advance / width))
        unused = 1.0 - util
        if is_last_line:
            score = unused * unused * 0.35
            if util < 0.30:
                score += (0.30 - util) ** 2 * 0.8
        else:
            score = unused * unused * 1.45
            if util < 0.55:
                score += (0.55 - util) ** 2 * 1.8

        if line[:1] in _LINE_START_PUNCTUATION:
            score += 2.6
        if line[-1:] in _LINE_END_PUNCTUATION:
            score += 1.8

        if len(line.strip()) <= 1:
            score += 1.2
        return score + 0.025

    def wrap_text_to_widths(
        self,
        text: str,
        widths: list[float],
        font: QFont,
        allow_char_break: bool = False,
    ) -> list[str] | None:
        metrics = QFontMetricsF(font)
        lines: list[str] = []
        line_index = 0

        def current_width() -> float | None:
            if line_index >= len(widths):
                return None
            return widths[line_index]

        paragraphs = text.split("\n")
        for paragraph_index, paragraph in enumerate(paragraphs):
            if paragraph_index > 0:
                if line_index >= len(widths):
                    return None
            if not paragraph.strip():
                lines.append("")
                line_index += 1
                continue

            words = paragraph.split(" ")
            current_line = ""
            word_index = 0
            while word_index < len(words):
                word = words[word_index]
                if not word:
                    word_index += 1
                    continue

                width = current_width()
                if width is None:
                    return None

                candidate = word if not current_line else current_line + " " + word
                if metrics.horizontalAdvance(candidate) <= width:
                    current_line = candidate
                    word_index += 1
                    continue

                if current_line:
                    lines.append(current_line)
                    line_index += 1
                    current_line = ""
                    continue

                if not allow_char_break:
                    return None

                char_line = ""
                for char in word:
                    width = current_width()
                    if width is None:
                        return None

                    candidate = char_line + char
                    if not char_line or metrics.horizontalAdvance(candidate) <= width:
                        char_line = candidate
                    else:
                        lines.append(char_line)
                        line_index += 1
                        char_line = char
                current_line = char_line
                word_index += 1

            if current_line:
                lines.append(current_line)
                line_index += 1

        return lines
