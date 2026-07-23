from __future__ import annotations

import hashlib
import json
import math
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF
from PySide6.QtGui import QColor, QColorSpace, QFont, QImage, QPainter, QTextLayout

from ...core.models import TextBubble
from ...infrastructure.image.text_layer_cache import TextLayerCache, TileCacheKey
from ...infrastructure.runtime.qt import QtRenderExecutor, QtWorkerState
from .service import RenderService


LAYOUT_CONTRACT = "qt-glyph-layout-v1"
PAINT_CONTRACT = "qt-alpha-stroke-v1"


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


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utf16_slice(text: str, start: int, end: int) -> str:
    raw = text.encode("utf-16-le", errors="surrogatepass")
    return raw[start * 2:end * 2].decode("utf-16-le", errors="replace")


def _stroke_color(text_color: str) -> str:
    value = text_color.lstrip("#")
    try:
        r, g, b = (int(value[index:index + 2], 16) / 255.0 for index in (0, 2, 4))
    except (ValueError, TypeError):
        return "#ffffff"

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
    return "#ffffff" if luminance < 0.5 else "#000000"


def _image_alpha(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    view = np.frombuffer(converted.bits(), dtype=np.uint8, count=converted.sizeInBytes())
    rows = view.reshape(converted.height(), converted.bytesPerLine())
    return rows[:, :converted.width() * 4].reshape(converted.height(), converted.width(), 4)[:, :, 3].copy()


def _qimage_from_rgba(rgba: np.ndarray) -> QImage:
    height, width = rgba.shape[:2]
    image = QImage(rgba.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
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
    ) -> None:
        self.render_service = render_service
        self.executor = executor
        self.cache = cache
        self.namespace = namespace
        self._request_lock = threading.RLock()
        self._request_inflight: dict[tuple[str, str, int, str, str], Future[TextLayerTile]] = {}

    def clear_runtime_caches(self) -> None:
        """Drop process-local derived assets after replacing a project."""
        # Stop new creators at the request gate and wait for creators already
        # accepted. This prevents an old request from repopulating the byte
        # cache immediately after a project replacement.
        with self._request_lock:
            pending = list(self._request_inflight.values())
            for future in pending:
                try:
                    future.result()
                except Exception:
                    pass
            self.executor.run(lambda worker: worker.clear())
            self.cache.clear()

    def layout_input_key(self, page_id: str, bubble: TextBubble, image: np.ndarray, image_revision: int) -> str:
        image_digest = hashlib.sha256(np.ascontiguousarray(image).data).hexdigest()
        return _canonical_hash({
            "contract": LAYOUT_CONTRACT,
            "page_id": page_id,
            "bubble_id": bubble.id,
            "image_shape": list(image.shape),
            "image_digest": image_digest,
            "image_visual_revision": image_revision,
            "source_text": bubble.text,
            "translated": bubble.translated,
            "box": bubble.box.to_xywh(),
            "text_box": bubble.text_box.to_xywh() if bubble.text_box else None,
            "layout_box": bubble.layout_box.to_xywh() if bubble.layout_box else None,
            "source_polygons": bubble.source_polygons,
            "text_class": bubble.text_class,
            "font_family": bubble.font_family,
            "font_size": bubble.font_size,
            "bold": bubble.bold,
            "italic": bubble.italic,
            "alignment": bubble.alignment,
            "writing_mode": bubble.writing_mode,
            "text_direction": bubble.text_direction,
            "justification": bubble.justification,
            "padding": bubble.layout_padding,
            "margin": bubble.layout_margin,
            "confidence": bubble.layout_confidence,
            "stroke_width_policy": "max(1,font/12)",
        })

    def create_tile(self, page_id: str, bubble: TextBubble, image: np.ndarray, image_revision: int = 0) -> TextLayerTile:
        input_key = self.layout_input_key(page_id, bubble, image, image_revision)
        paint_input = {"text_color": bubble.color.lower(), "stroke_color": "relative-luminance-v1", "contract": PAINT_CONTRACT}
        request_key = (self.namespace, page_id, bubble.id, input_key, _canonical_hash(paint_input))
        with self._request_lock:
            pending = self._request_inflight.get(request_key)
            owner = pending is None
            if owner:
                pending = Future()
                self._request_inflight[request_key] = pending
        assert pending is not None
        if not owner:
            return pending.result()

        def build(worker: QtWorkerState) -> TextLayerTile:
            artifact = worker.shaped_layout_cache.get(input_key)
            if artifact is None:
                artifact = self._shape_layout(worker, page_id, bubble, image, input_key)
                worker.shaped_layout_cache[input_key] = artifact
                if len(worker.shaped_layout_cache) > 2048:
                    worker.shaped_layout_cache.pop(next(iter(worker.shaped_layout_cache)))
            return self._paint_artifact(artifact, page_id, bubble, paint_input)

        # Render fingerprint becomes available after actual fallback font runs
        # have been shaped, so singleflight is applied to the final tile after
        # the worker returns it. Concurrent callers still share executor order;
        # API-level regeneration uses the cache's final key.
        try:
            tile = self.executor.run(build)
            key = TileCacheKey(self.namespace, page_id, bubble.id, tile.render_fingerprint)
            tile = self.cache.get_or_create(key, lambda: tile)
            pending.set_result(tile)
            return tile
        except BaseException as exc:
            pending.set_exception(exc)
            raise
        finally:
            with self._request_lock:
                self._request_inflight.pop(request_key, None)

    def _shape_layout(
        self,
        worker: QtWorkerState,
        page_id: str,
        bubble: TextBubble,
        image: np.ndarray,
        input_key: str,
    ) -> dict[str, Any]:
        legacy = self.render_service._get_layout_for_bubble_worker(
            bubble.translated or bubble.text or "",
            bubble,
            image=image,
            font_family=bubble.font_family or None,
        )
        font = QFont(legacy.font)
        font.setBold(bubble.bold)
        font.setItalic(bubble.italic)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
        font_size = max(1, int(font.pixelSize()))
        stroke_width = max(1.0, font_size / 12.0)
        flags = (
            QTextLayout.GlyphRunRetrievalFlag.RetrieveGlyphIndexes
            | QTextLayout.GlyphRunRetrievalFlag.RetrieveGlyphPositions
            | QTextLayout.GlyphRunRetrievalFlag.RetrieveStringIndexes
            | QTextLayout.GlyphRunRetrievalFlag.RetrieveString
        )
        lines: list[dict[str, Any]] = []
        font_identities: list[dict[str, Any]] = []
        for slot in legacy.line_layouts:
            text = slot.text
            qlayout = QTextLayout(text, font, worker.metric_device)
            qlayout.beginLayout()
            qline = qlayout.createLine()
            if not qline.isValid():
                qlayout.endLayout()
                continue
            qline.setLineWidth(max(1.0, float(slot.width)))
            qlayout.endLayout()
            advance = float(qline.naturalTextWidth())
            if bubble.alignment == "right":
                origin_x = float(slot.x + max(0.0, slot.width - advance))
            elif bubble.alignment == "left":
                origin_x = float(slot.x)
            else:
                origin_x = float(slot.x + max(0.0, (slot.width - advance) / 2.0))
            baseline_y = float(slot.y + qline.ascent())
            # PySide 6.8 on Windows corrupts the rawFont wrapper when retrieval
            # flags carrying QString metadata are mixed with rawFont(). Keep
            # the explicitly requested source metadata runs separate from the
            # default paint runs and pair them by Qt's stable run order.
            paint_runs = list(qline.glyphRuns())
            # Capture thread-local raw-font identities before asking the
            # binding for QString metadata runs (see note below).
            metadata_runs = list(qline.glyphRuns(-1, -1, flags))
            starts = sorted(
                min(int(index) for index in run.stringIndexes())
                for run in metadata_runs
                if run.stringIndexes()
            )
            total_units = len(text.encode("utf-16-le", errors="surrogatepass")) // 2
            run_dtos = []
            for run_index, run in enumerate(paint_runs):
                metadata_run = metadata_runs[run_index] if run_index < len(metadata_runs) else None
                indexes = [int(index) for index in metadata_run.stringIndexes()] if metadata_run is not None else []
                start = min(indexes) if indexes else 0
                end = min((value for value in starts if value > start), default=total_units)
                family = font.family()
                positions = list(run.positions())
                run_origin_x = origin_x + (min((point.x() for point in positions), default=0.0))
                run_dtos.append({
                    "text": _utf16_slice(text, start, end),
                    "origin_x": run_origin_x,
                    "font_family": family,
                    "font_pixel_size": float(font_size),
                    "is_rtl": bool(run.isRightToLeft()),
                    "_run": run,
                })
                font_identities.append({
                    "family": family,
                    "pixel_size": float(font_size),
                    "font_digest": "resolved-by-raster-alpha",
                    "glyph_indexes": [int(value) for value in run.glyphIndexes()],
                    "positions": [[round(point.x(), 6), round(point.y(), 6)] for point in positions],
                })
            lines.append({
                "text": text,
                "origin_x": origin_x,
                "baseline_y": baseline_y,
                "_draw_origin_y": float(slot.y),
                "advance_width": advance,
                "runs": run_dtos,
            })

        layout_fingerprint = _canonical_hash({
            "input_key": input_key,
            "fonts": font_identities,
            "lines": [{key: value for key, value in line.items() if key != "runs"} for line in lines],
        })
        return {
            "layout_fingerprint": layout_fingerprint,
            "font_family": font.family(),
            "font_size": font_size,
            "stroke_width": stroke_width,
            "overflow": bool(legacy.is_overflow),
            "reached_min_font": bool(legacy.reached_min_font),
            "line_height_ratio": float(legacy.line_height_ratio),
            "area_usage": float(legacy.area_usage),
            "page_width": int(image.shape[1]),
            "page_height": int(image.shape[0]),
            "lines": lines,
        }

    def _paint_artifact(self, artifact: dict[str, Any], page_id: str, bubble: TextBubble, paint_input: dict[str, Any]) -> TextLayerTile:
        stroke_width = float(artifact["stroke_width"])
        pad = int(math.ceil(stroke_width)) + 4
        lines = artifact["lines"]
        if not lines:
            raise RuntimeError("TEXT_LAYER_EMPTY")
        rough_left = min(float(line["origin_x"]) for line in lines) - pad
        rough_top = min(float(line["baseline_y"]) - artifact["font_size"] * 1.5 for line in lines) - pad
        rough_right = max(float(line["origin_x"]) + float(line["advance_width"]) for line in lines) + pad
        rough_bottom = max(float(line["baseline_y"]) + artifact["font_size"] * 0.6 for line in lines) + pad
        surface_x = int(math.floor(rough_left))
        surface_y = int(math.floor(rough_top))
        width = max(1, int(math.ceil(rough_right)) - surface_x)
        height = max(1, int(math.ceil(rough_bottom)) - surface_y)
        if width * height > 64_000_000:
            raise RuntimeError("TEXT_LAYER_TOO_LARGE")

        fill_image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        fill_image.setDevicePixelRatio(1.0)
        fill_image.fill(0)
        painter = QPainter(fill_image)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(QColor(255, 255, 255, 255))
        line_alphas: list[np.ndarray] = []
        for line in lines:
            line_image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            line_image.fill(0)
            line_painter = QPainter(line_image)
            line_painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            line_painter.setPen(QColor(255, 255, 255, 255))
            base = QPointF(float(line["origin_x"]) - surface_x, float(line["_draw_origin_y"]) - surface_y)
            for run_dto in line["runs"]:
                run = run_dto["_run"]
                painter.drawGlyphRun(base, run)
                line_painter.drawGlyphRun(base, run)
            line_painter.end()
            line_alphas.append(_image_alpha(line_image))
        painter.end()
        fill_alpha = _image_alpha(fill_image)
        alpha_identity = hashlib.sha256(
            width.to_bytes(4, "big") + height.to_bytes(4, "big") + fill_alpha.tobytes()
        ).hexdigest()
        if artifact.get("alpha_identity") != alpha_identity:
            artifact["alpha_identity"] = alpha_identity
            artifact["layout_fingerprint"] = _canonical_hash({
                "shaped_layout": artifact["layout_fingerprint"],
                "actual_fallback_raster_alpha": alpha_identity,
            })
        support = (fill_alpha > 0).astype(np.uint8)
        inverse = (support == 0).astype(np.uint8)
        distance = cv2.distanceTransform(inverse, cv2.DIST_L2, 5)
        expanded = np.where(support > 0, 255.0, np.clip(stroke_width + 0.5 - distance, 0.0, 1.0) * 255.0).astype(np.uint8)
        stroke_only = np.maximum(expanded.astype(np.int16) - fill_alpha.astype(np.int16), 0).astype(np.uint8)

        text_color = QColor(bubble.color if QColor(bubble.color).isValid() else "#000000")
        stroke_hex = _stroke_color(text_color.name())
        stroke_color = QColor(stroke_hex)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        # Premultiplied color assembly followed by straight-alpha conversion.
        stroke_a = stroke_only.astype(np.float32) / 255.0
        fill_a = fill_alpha.astype(np.float32) / 255.0
        out_a = fill_a + stroke_a * (1.0 - fill_a)
        for channel, (fill_value, stroke_value) in enumerate(zip(
            (text_color.red(), text_color.green(), text_color.blue()),
            (stroke_color.red(), stroke_color.green(), stroke_color.blue()),
        )):
            premul = fill_value * fill_a + stroke_value * stroke_a * (1.0 - fill_a)
            rgba[:, :, channel] = np.where(out_a > 0, np.clip(premul / np.maximum(out_a, 1e-6), 0, 255), 0).astype(np.uint8)
        rgba[:, :, 3] = np.clip(out_a * 255.0, 0, 255).astype(np.uint8)

        visible = rgba[:, :, 3] > 0
        if not bool(visible.any()):
            raise RuntimeError("TEXT_LAYER_EMPTY")
        ys, xs = np.where(visible)
        alpha_left = surface_x + int(xs.min())
        alpha_top = surface_y + int(ys.min())
        alpha_right = surface_x + int(xs.max()) + 1
        alpha_bottom = surface_y + int(ys.max()) + 1
        if (
            alpha_left < 0 or alpha_top < 0
            or alpha_right > artifact["page_width"]
            or alpha_bottom > artifact["page_height"]
        ):
            raise RuntimeError("TEXT_LAYER_PAGE_OVERFLOW")
        left = max(0, int(xs.min()) - 2)
        top = max(0, int(ys.min()) - 2)
        right = min(width, int(xs.max()) + 3)
        bottom = min(height, int(ys.max()) + 3)
        left = max(left, -surface_x)
        top = max(top, -surface_y)
        right = min(right, artifact["page_width"] - surface_x)
        bottom = min(bottom, artifact["page_height"] - surface_y)
        crop_x, crop_y = surface_x + left, surface_y + top
        crop_width, crop_height = right - left, bottom - top
        if crop_width <= 0 or crop_height <= 0:
            raise RuntimeError("TEXT_LAYER_PAGE_OVERFLOW")
        cropped = np.ascontiguousarray(rgba[top:bottom, left:right])

        public_lines = []
        for line, line_alpha in zip(lines, line_alphas):
            expanded_line = np.maximum(line_alpha, np.where(
                cv2.distanceTransform((line_alpha == 0).astype(np.uint8), cv2.DIST_L2, 5) <= stroke_width,
                255,
                0,
            ).astype(np.uint8))
            line_visible = expanded_line > 0
            line_ys, line_xs = np.where(line_visible)
            if line_xs.size:
                ink_left = surface_x + int(line_xs.min())
                ink_top = surface_y + int(line_ys.min())
                ink_width = int(line_xs.max() - line_xs.min() + 1)
                ink_height = int(line_ys.max() - line_ys.min() + 1)
            else:
                ink_left = int(round(line["origin_x"]))
                ink_top = int(round(line["baseline_y"]))
                ink_width = ink_height = 0
            public_lines.append({
                "text": line["text"],
                "origin_x": round(float(line["origin_x"]) * 64) / 64,
                "baseline_y": round(float(line["baseline_y"]) * 64) / 64,
                "advance_width": round(float(line["advance_width"]) * 64) / 64,
                "ink_left": ink_left,
                "ink_top": ink_top,
                "ink_width": ink_width,
                "ink_height": ink_height,
                "runs": [{key: value for key, value in run.items() if key != "_run"} for run in line["runs"]],
            })
        layout_dto = {
            "font_mode": "fixed" if bubble.font_size > 0 else "auto",
            "requested_font_size": bubble.font_size if bubble.font_size > 0 else None,
            "font_size": artifact["font_size"],
            "font_family": artifact["font_family"],
            "overflow": artifact["overflow"],
            "reached_min_font": artifact["reached_min_font"],
            "line_height_ratio": artifact["line_height_ratio"],
            "area_usage": artifact["area_usage"],
            "lines": public_lines,
        }
        render_fingerprint = _canonical_hash({
            "layout_fingerprint": artifact["layout_fingerprint"],
            "paint": paint_input,
            "stroke_color": stroke_hex,
        })
        png_bytes = _encode_png(cropped)
        pixel_digest = hashlib.sha256(
            crop_width.to_bytes(4, "big") + crop_height.to_bytes(4, "big") + cropped.tobytes()
        ).hexdigest()
        return TextLayerTile(
            page_id=page_id,
            bubble_id=bubble.id,
            layout_fingerprint=artifact["layout_fingerprint"],
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
