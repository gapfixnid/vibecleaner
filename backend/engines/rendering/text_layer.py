from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QColorSpace, QImage

from ...core.models import TextBubble
from ...infrastructure.image.canonical_layout_cache import CanonicalLayoutCache
from ...infrastructure.image.text_layer_cache import TextLayerCache, TileCacheKey
from ...infrastructure.runtime.qt import QtRenderExecutor, QtWorkerState
from .canonical_layout import (
    CanonicalLayoutArtifact,
    CanonicalLayoutSelector,
    canonical_hash,
)
from .service import RenderService


PAINT_CONTRACT = "qt-alpha-stroke-v2"


@dataclass(frozen=True)
class TextLayerTile:
    page_id: str
    bubble_id: int
    layout_fingerprint: str
    render_fingerprint: str
    cache_key: str
    pixel_digest: str
    crop_x: int
    crop_y: int
    width: int
    height: int
    png_bytes: bytes
    layout: dict[str, Any]
    stroke_color: str
    stroke_width: float


def _stroke_color(text_color: str) -> str:
    value = text_color.lstrip("#")
    try:
        r, g, b = (
            int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4)
        )
    except (ValueError, TypeError):
        return "#ffffff"

    def linear(channel: float) -> float:
        return (
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )

    luminance = (
        0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
    )
    return "#ffffff" if luminance < 0.5 else "#000000"


def _qimage_from_rgba(rgba: np.ndarray) -> QImage:
    height, width = rgba.shape[:2]
    image = QImage(
        rgba.data,
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()
    image.setDevicePixelRatio(1.0)
    image.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
    return image


def _encode_png(rgba: np.ndarray) -> bytes:
    image = _qimage_from_rgba(rgba)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("TEXT_LAYER_PNG_ENCODE_FAILED")
    buffer.close()
    return bytes(data)


class TextLayerService:
    def __init__(
        self,
        render_service: RenderService,
        executor: QtRenderExecutor,
        cache: TextLayerCache[TextLayerTile],
        namespace: str,
        canonical_selector: CanonicalLayoutSelector | None = None,
    ) -> None:
        self.render_service = render_service
        self.executor = executor
        self.cache = cache
        self.namespace = namespace
        if canonical_selector is None:
            canonical_selector = CanonicalLayoutSelector(
                render_service,
                executor,
                CanonicalLayoutCache(executor),
            )
        self.canonical_selector = canonical_selector
        self.render_service.set_canonical_selector(canonical_selector)

    def clear_runtime_caches(self) -> None:
        """Drop process-local derived assets after replacing a project."""
        self.cache.clear(wait=True)
        self.canonical_selector.cache.clear(wait=True)
        self.executor.run(lambda worker: worker.clear())

    def layout_input_key(
        self,
        page_id: str,
        bubble: TextBubble,
        image: np.ndarray,
        image_revision: int,
    ) -> str:
        del page_id, image_revision
        text = bubble.translated or bubble.text or ""
        return self.canonical_selector.build_input_key(
            text,
            bubble,
            image,
            bubble.font_family or None,
        )

    def create_tile(
        self,
        page_id: str,
        bubble: TextBubble,
        image: np.ndarray,
        image_revision: int = 0,
    ) -> TextLayerTile:
        text = bubble.translated or bubble.text or ""
        input_key = self.layout_input_key(
            page_id, bubble, image, image_revision
        )
        request = self.canonical_selector.build_request(
            text,
            bubble,
            image,
            bubble.font_family or None,
            input_key=input_key,
        )
        artifact = self.canonical_selector.get_artifact(request)
        text_color = QColor(
            bubble.color if QColor(bubble.color).isValid() else "#000000"
        )
        stroke_hex = _stroke_color(text_color.name())
        paint_input = {
            "text_color": text_color.name().lower(),
            "stroke_color": stroke_hex,
            "contract": PAINT_CONTRACT,
        }
        render_fingerprint = canonical_hash(
            {
                "layout_fingerprint": artifact.layout_fingerprint,
                "paint": paint_input,
            }
        )
        key = TileCacheKey(
            self.namespace,
            page_id,
            bubble.id,
            render_fingerprint,
        )
        # The cache owns the complete paint/encode task. Concurrent misses for
        # this final key therefore execute color composition and PNG encoding
        # exactly once.
        return self.cache.get_or_create(
            key,
            lambda: self.executor.run(
                lambda worker: self._paint_artifact(
                    worker,
                    artifact,
                    page_id,
                    bubble.id,
                    text_color,
                    stroke_hex,
                    render_fingerprint,
                )
            ),
        )

    def _paint_artifact(
        self,
        _worker: QtWorkerState,
        artifact: CanonicalLayoutArtifact,
        page_id: str,
        bubble_id: int,
        text_color: QColor,
        stroke_hex: str,
        render_fingerprint: str,
    ) -> TextLayerTile:
        selected = artifact.selected
        fill_alpha = selected.fill_alpha
        stroke_only_alpha = selected.stroke_only_alpha
        if fill_alpha.shape != stroke_only_alpha.shape:
            raise RuntimeError("TEXT_LAYER_ALPHA_SHAPE_MISMATCH")

        height, width = fill_alpha.shape
        if width * height > 64_000_000:
            raise RuntimeError("TEXT_LAYER_TOO_LARGE")

        # stroke_only_alpha is exactly expanded_alpha - fill_alpha. Compose
        # stroke behind the fill once, using integer source-over arithmetic.
        fill_u16 = fill_alpha.astype(np.uint16)
        stroke_u16 = stroke_only_alpha.astype(np.uint16)
        out_alpha_u16 = fill_u16 + (
            stroke_u16 * (255 - fill_u16)
        ) // 255
        out_alpha = np.clip(out_alpha_u16, 0, 255).astype(np.uint8)
        visible = out_alpha > 0
        if not bool(visible.any()):
            raise RuntimeError("TEXT_LAYER_EMPTY")

        stroke_color = QColor(stroke_hex)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        fill_a = fill_u16.astype(np.uint32)
        stroke_behind = (
            stroke_u16.astype(np.uint32) * (255 - fill_u16)
        ) // 255
        out_a32 = np.maximum(out_alpha_u16.astype(np.uint32), 1)
        for channel, (fill_value, stroke_value) in enumerate(
            zip(
                (
                    text_color.red(),
                    text_color.green(),
                    text_color.blue(),
                ),
                (
                    stroke_color.red(),
                    stroke_color.green(),
                    stroke_color.blue(),
                ),
            )
        ):
            premultiplied = fill_value * fill_a + stroke_value * stroke_behind
            rgba[:, :, channel] = np.where(
                out_alpha_u16 > 0,
                np.clip(
                    (premultiplied + out_a32 // 2) // out_a32,
                    0,
                    255,
                ),
                0,
            ).astype(np.uint8)
        rgba[:, :, 3] = out_alpha

        ys, xs = np.where(visible)
        surface_x = selected.surface_x
        surface_y = selected.surface_y
        alpha_left = surface_x + int(xs.min())
        alpha_top = surface_y + int(ys.min())
        alpha_right = surface_x + int(xs.max()) + 1
        alpha_bottom = surface_y + int(ys.max()) + 1
        if (
            alpha_left < 0
            or alpha_top < 0
            or alpha_right > artifact.page_width
            or alpha_bottom > artifact.page_height
        ):
            raise RuntimeError("TEXT_LAYER_PAGE_OVERFLOW")

        left = max(0, int(xs.min()) - 2, -surface_x)
        top = max(0, int(ys.min()) - 2, -surface_y)
        right = min(
            width,
            int(xs.max()) + 3,
            artifact.page_width - surface_x,
        )
        bottom = min(
            height,
            int(ys.max()) + 3,
            artifact.page_height - surface_y,
        )
        crop_width = right - left
        crop_height = bottom - top
        if crop_width <= 0 or crop_height <= 0:
            raise RuntimeError("TEXT_LAYER_PAGE_OVERFLOW")
        crop_x = surface_x + left
        crop_y = surface_y + top
        cropped = np.ascontiguousarray(rgba[top:bottom, left:right])

        lines = [
            {
                "text": line.text,
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
            for line in selected.shaped_lines
        ]
        spec = selected.candidate
        layout_dto = {
            "font_mode": "fixed"
            if spec.mask_pass == "fixed"
            else "auto",
            "requested_font_size": spec.effective_font_size
            if spec.mask_pass == "fixed"
            else None,
            "font_size": spec.effective_font_size,
            "font_family": spec.font_family,
            "overflow": bool(
                spec.is_overflow
                or not selected.diagnostics.raster_safe
            ),
            "reached_min_font": spec.reached_min_font,
            "line_height_ratio": spec.line_height_ratio,
            "area_usage": spec.area_usage,
            "lines": lines,
            "diagnostics": dict(artifact.diagnostics),
        }
        png_bytes = _encode_png(cropped)
        pixel_digest = hashlib.sha256(
            crop_width.to_bytes(4, "big")
            + crop_height.to_bytes(4, "big")
            + cropped.tobytes()
        ).hexdigest()
        stroke_width = max(1.0, spec.effective_font_size / 12.0)
        return TextLayerTile(
            page_id=page_id,
            bubble_id=bubble_id,
            layout_fingerprint=artifact.layout_fingerprint,
            render_fingerprint=render_fingerprint,
            cache_key=render_fingerprint[:24],
            pixel_digest=pixel_digest,
            crop_x=crop_x,
            crop_y=crop_y,
            width=crop_width,
            height=crop_height,
            png_bytes=png_bytes,
            layout=layout_dto,
            stroke_color=stroke_hex,
            stroke_width=stroke_width,
        )
