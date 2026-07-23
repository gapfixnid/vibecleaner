from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Literal

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QTextLayout

from ...core.models import TextBubble
from ...infrastructure.fonts import resolver as font_resolver
from ...infrastructure.image.canonical_layout_cache import CanonicalLayoutCache
from ...infrastructure.runtime.qt import QtRenderExecutor, QtWorkerState
from .alpha import compose_final_alpha
from .renderer import TextLayoutResult, TextLineLayout, _set_font_pixel_size, font_pixel_size
from .service import FontDescriptor, PublicTextLayoutResult, RenderService, _to_qrectf


LAYOUT_CONTRACT = "qt-glyph-layout-v3"
MAX_RASTER_CANDIDATES = 8
MAX_SURFACE_PIXELS = 64_000_000
MAX_TRANSIENT_BYTES = 96 * 1024 * 1024


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CanonicalPublicLine:
    text: str
    x: float
    y: float
    width: float
    height: float
    origin_x: float | None = None
    baseline_y: float | None = None
    advance_width: float | None = None
    ink_left: int | None = None
    ink_top: int | None = None
    ink_width: int | None = None
    ink_height: int | None = None
    runs: tuple[CanonicalRun, ...] = ()


@dataclass(frozen=True)
class CanonicalRun:
    text: str
    origin_x: float
    font_family: str
    font_pixel_size: float
    is_rtl: bool


@dataclass(frozen=True)
class CanonicalShapedLine:
    text: str
    origin_x: float
    baseline_y: float
    advance_width: float
    ink_left: int
    ink_top: int
    ink_width: int
    ink_height: int
    runs: tuple[CanonicalRun, ...]


@dataclass(frozen=True)
class CandidateDiagnostics:
    effective_font_size: int
    mask_pass: str
    allow_char_break: bool
    raster_safe: bool
    outside_alpha_ratio: float
    outside_visible_pixels: int
    resource_violation: bool = False


@dataclass(frozen=True)
class RoughLayoutCandidate:
    font_family: str
    effective_font_size: int
    bold: bool
    italic: bool
    line_height_ratio: float
    mask_pass: Literal["mask_strict", "mask_relaxed", "rect", "fixed", "overflow_fallback"]
    allow_char_break: bool
    lines: tuple[str, ...]
    slots: tuple[CanonicalPublicLine, ...]
    score: float
    area_usage: float
    reached_min_font: bool
    is_overflow: bool
    rough_key: tuple[Any, ...]


@dataclass(frozen=True)
class RasterizedCandidate:
    candidate: RoughLayoutCandidate
    fill_alpha: np.ndarray
    stroke_only_alpha: np.ndarray
    surface_x: int
    surface_y: int
    shaped_lines: tuple[CanonicalShapedLine, ...]
    font_identities: tuple[dict[str, Any], ...]
    diagnostics: CandidateDiagnostics

    @property
    def byte_size(self) -> int:
        return int(self.fill_alpha.nbytes + self.stroke_only_alpha.nbytes)


@dataclass(frozen=True)
class CanonicalLayoutArtifact:
    selected: RasterizedCandidate
    public_layout: PublicTextLayoutResult
    layout_fingerprint: str
    font_identities: tuple[dict[str, Any], ...]
    diagnostics: dict[str, Any]
    page_width: int
    page_height: int

    @property
    def byte_size(self) -> int:
        layout_bytes = len(repr(self.public_layout).encode("utf-8"))
        font_bytes = len(repr(self.font_identities).encode("utf-8"))
        return self.selected.byte_size + layout_bytes + font_bytes


@dataclass(frozen=True)
class BubbleLayoutRequest:
    input_key: str
    text: str
    bubble: TextBubble
    image: np.ndarray | None
    font_family: str | None
    mask: np.ndarray | None
    mask_bounds: tuple[int, int, int, int] | None
    mask_source: str | None
    layout_rect: QRectF
    target_center_y: float | None
    automatic_min_size: float
    page_width: int
    page_height: int


def _utf16_slice(text: str, start: int, end: int) -> str:
    raw = text.encode("utf-16-le", errors="surrogatepass")
    return raw[start * 2 : end * 2].decode("utf-16-le", errors="replace")


def _expanded_alpha(fill_alpha: np.ndarray, stroke_width: float) -> np.ndarray:
    support = (fill_alpha > 0).astype(np.uint8)
    inverse = (support == 0).astype(np.uint8)
    distance = cv2.distanceTransform(inverse, cv2.DIST_L2, 5)
    return np.where(
        support > 0,
        255.0,
        np.clip(stroke_width + 0.5 - distance, 0.0, 1.0) * 255.0,
    ).astype(np.uint8)


def _stroke_only(fill_alpha: np.ndarray, stroke_width: float) -> np.ndarray:
    expanded = _expanded_alpha(fill_alpha, stroke_width)
    return np.maximum(
        expanded.astype(np.int16) - fill_alpha.astype(np.int16), 0
    ).astype(np.uint8)


class CanonicalLayoutSelector:
    def __init__(
        self,
        render_service: RenderService,
        executor: QtRenderExecutor,
        cache: CanonicalLayoutCache[CanonicalLayoutArtifact],
    ) -> None:
        self.render_service = render_service
        self.renderer = render_service.renderer
        self.executor = executor
        self.cache = cache

    def build_input_key(
        self,
        text: str,
        bubble: TextBubble,
        image: np.ndarray | None,
        font_family: str | None = None,
        *,
        mask: np.ndarray | None = None,
        mask_bounds: tuple[int, int, int, int] | None = None,
        mask_source: str | None = None,
    ) -> str:
        if mask is None:
            body = self.render_service._build_bubble_body_mask(
                bubble, image
            )
            mask = body.mask if body is not None else None
            mask_bounds = body.bounds if body is not None else None
            mask_source = body.source if body is not None else None
        image_digest = (
            hashlib.sha256(np.ascontiguousarray(image).data).hexdigest()
            if image is not None
            else None
        )
        mask_array = np.ascontiguousarray(mask) if mask is not None else None
        mask_digest = (
            hashlib.sha256(mask_array.data).hexdigest()
            if mask_array is not None
            else None
        )
        return canonical_hash(
            {
                "contract": LAYOUT_CONTRACT,
                "text": text,
                "source_text": bubble.text,
                "image_shape": list(image.shape) if image is not None else None,
                "image_digest": image_digest,
                "body_mask_shape": list(mask_array.shape)
                if mask_array is not None
                else None,
                "body_mask_digest": mask_digest,
                "body_mask_bounds": mask_bounds,
                "body_mask_source": mask_source,
                "body_mask_contract": "bubble-clip-v3",
                "bubble_id": bubble.id,
                "box": bubble.box.to_xywh(),
                "text_box": bubble.text_box.to_xywh() if bubble.text_box else None,
                "layout_box": bubble.layout_box.to_xywh()
                if bubble.layout_box
                else None,
                "source_polygons": bubble.source_polygons,
                "text_class": bubble.text_class,
                "font_family": font_family or bubble.font_family,
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
                "qt_raster": "grayscale-antialias-no-subpixel-v2",
            }
        )

    def build_request(
        self,
        text: str,
        bubble: TextBubble,
        image: np.ndarray | None,
        font_family: str | None,
        *,
        input_key: str | None = None,
    ) -> BubbleLayoutRequest:
        body = self.render_service._build_bubble_body_mask(
            bubble, image
        )
        mask = body.mask if body is not None else None
        mask_bounds = body.bounds if body is not None else None
        mask_source = body.source if body is not None else None
        input_key = input_key or self.build_input_key(
            text,
            bubble,
            image,
            font_family,
            mask=mask,
            mask_bounds=mask_bounds,
            mask_source=mask_source,
        )
        layout_rect = self.render_service._text_layout_rect(bubble)
        target = self.render_service._target_center_y(
            text,
            bubble,
            mask,
            mask_origin_y=(
                float(mask_bounds[1])
                if mask_bounds is not None
                else None
            ),
        )
        if image is not None and image.ndim >= 2:
            page_height, page_width = image.shape[:2]
        else:
            page_width = max(1, int(math.ceil(bubble.box.right)))
            page_height = max(1, int(math.ceil(bubble.box.bottom)))
        return BubbleLayoutRequest(
            input_key=input_key,
            text=text,
            bubble=deepcopy(bubble),
            image=image,
            font_family=font_family,
            mask=mask,
            mask_bounds=mask_bounds,
            mask_source=mask_source,
            layout_rect=layout_rect,
            target_center_y=target,
            automatic_min_size=self.render_service._automatic_min_font_size(image),
            page_width=int(page_width),
            page_height=int(page_height),
        )

    def select(self, request: BubbleLayoutRequest) -> PublicTextLayoutResult:
        return self.get_artifact(request).public_layout

    def get_artifact(self, request: BubbleLayoutRequest) -> CanonicalLayoutArtifact:
        return self.cache.get_or_create(
            request.input_key,
            lambda: self.executor.run(
                lambda worker: self.select_in_worker(worker, request)
            ),
        )

    def select_in_worker(
        self, worker: QtWorkerState, request: BubbleLayoutRequest
    ) -> CanonicalLayoutArtifact:
        candidates = self._collect_candidates(request)
        if not candidates:
            candidates = [self._fallback_candidate(request)]
        candidates = sorted(
            candidates,
            key=lambda item: (
                -item.effective_font_size,
                item.mask_pass,
                item.allow_char_break,
                item.rough_key,
            ),
        )[:MAX_RASTER_CANDIDATES]
        raster_diagnostics: list[CandidateDiagnostics] = []
        best: RasterizedCandidate | None = None
        overflow_best: RasterizedCandidate | None = None
        fmax: int | None = None
        strict_max: int | None = None
        relaxed_max: int | None = None

        for candidate in candidates:
            retained = {
                id(item.fill_alpha): item
                for item in (best, overflow_best)
                if item is not None
                and not item.diagnostics.resource_violation
            }
            retained_bytes = sum(item.byte_size for item in retained.values())
            rasterized = self._rasterize_candidate(
                worker,
                request,
                candidate,
                transient_budget=max(
                    0, MAX_TRANSIENT_BYTES - retained_bytes
                ),
            )
            raster_diagnostics.append(rasterized.diagnostics)
            if (
                not rasterized.diagnostics.resource_violation
                and (
                    overflow_best is None
                    or (
                        rasterized.diagnostics.outside_alpha_ratio,
                        -rasterized.candidate.effective_font_size,
                    )
                    < (
                        overflow_best.diagnostics.outside_alpha_ratio,
                        -overflow_best.candidate.effective_font_size,
                    )
                )
            ):
                overflow_best = rasterized
            if not rasterized.diagnostics.raster_safe:
                continue
            size = candidate.effective_font_size
            if candidate.mask_pass == "mask_strict":
                strict_max = max(strict_max or 0, size)
            elif candidate.mask_pass == "mask_relaxed":
                relaxed_max = max(relaxed_max or 0, size)
            if fmax is None:
                fmax = size
            threshold = int(math.ceil(fmax * 0.94))
            if size < threshold:
                continue
            if best is None or self._final_key(rasterized) < self._final_key(best):
                best = rasterized

        if best is None:
            if overflow_best is None:
                fallback = next(
                    (
                        item
                        for item in candidates
                        if item.mask_pass == "overflow_fallback"
                    ),
                    None,
                )
                if fallback is None:
                    fallback = self._fallback_candidate(request)
                    candidates.append(fallback)
                best = self._resource_failure(fallback)
                raster_diagnostics.append(best.diagnostics)
            else:
                best = overflow_best
            fmax = best.candidate.effective_font_size

        return self._freeze_artifact(
            request,
            best,
            candidates,
            raster_diagnostics,
            fmax or best.candidate.effective_font_size,
            strict_max,
            relaxed_max,
        )

    def _resolve_family(self, request: BubbleLayoutRequest) -> str:
        if request.font_family:
            return request.font_family
        resolved, _chain = font_resolver.resolve(request.text, target_lang="Korean")
        return resolved.name

    @staticmethod
    def _mask_rect(request: BubbleLayoutRequest) -> QRectF:
        if request.mask_bounds is None:
            return _to_qrectf(request.bubble.box)
        x1, y1, x2, y2 = request.mask_bounds
        return QRectF(x1, y1, x2 - x1, y2 - y1)

    @staticmethod
    def _to_spec(
        layout: TextLayoutResult,
        *,
        mask_pass: str,
        allow_char_break: bool,
        bold: bool,
        italic: bool,
        rough_key: tuple[Any, ...],
    ) -> RoughLayoutCandidate:
        return RoughLayoutCandidate(
            font_family=layout.font.family(),
            effective_font_size=font_pixel_size(layout.font),
            bold=bold,
            italic=italic,
            line_height_ratio=float(layout.line_height_ratio),
            mask_pass=mask_pass,  # type: ignore[arg-type]
            allow_char_break=allow_char_break,
            lines=tuple(layout.lines),
            slots=tuple(
                CanonicalPublicLine(line.text, line.x, line.y, line.width, line.height)
                for line in layout.line_layouts
            ),
            score=float(layout.score),
            area_usage=float(layout.area_usage),
            reached_min_font=bool(layout.reached_min_font),
            is_overflow=bool(layout.is_overflow),
            rough_key=rough_key,
        )

    def _collect_candidates(self, request: BubbleLayoutRequest) -> list[RoughLayoutCandidate]:
        bubble = request.bubble
        family = self._resolve_family(request)
        bold = bool(bubble.bold)
        italic = bool(bubble.italic)
        requested = int(bubble.font_size or 0)
        padding = dict(bubble.layout_padding or {})
        margin = dict(bubble.layout_margin or {})
        alignment = bubble.alignment or "center"

        if requested > 0:
            rect = (
                self._mask_rect(request)
                if request.mask is not None
                else request.layout_rect
            )
            layout = self.renderer.layout_text_at_fixed_size(
                request.text,
                rect,
                requested,
                mask=request.mask,
                font_family=family,
                alignment=alignment,
                padding=padding,
                margin=margin,
                target_center_y=request.target_center_y,
                bold=bold,
                italic=italic,
            )
            return [
                self._to_spec(
                    layout,
                    mask_pass="fixed",
                    allow_char_break=True,
                    bold=bold,
                    italic=italic,
                    rough_key=(bool(layout.is_overflow), -requested),
                )
            ]

        if request.mask is None:
            content_rect = self.renderer.content_rect(
                request.layout_rect,
                padding=padding,
                margin=margin,
            )
            minimum = self.renderer._automatic_min_font_size(
                request.automatic_min_size,
                self.render_service._max_font_size(),
            )
            dynamic_max = max(
                minimum,
                min(
                    self.render_service._max_font_size(),
                    content_rect.height() * 0.70,
                    content_rect.width() * 0.70,
                ),
            )
            sizes = self.renderer._candidate_font_sizes(
                minimum, dynamic_max
            )
            chosen: list[RoughLayoutCandidate] = []
            for allow_break in (False, True):
                pass_candidates: list[RoughLayoutCandidate] = []
                for size in sizes:
                    layout = self.renderer._best_rect_layout_for_candidates(
                        request.text,
                        content_rect,
                        family,
                        [size],
                        alignment,
                        minimum,
                        allow_break,
                        bold=bold,
                        italic=italic,
                    )
                    if layout is None:
                        continue
                    pass_candidates.append(
                        self._to_spec(
                            layout,
                            mask_pass="rect",
                            allow_char_break=allow_break,
                            bold=bold,
                            italic=italic,
                            rough_key=(
                                bool(layout.is_overflow),
                                -font_pixel_size(layout.font),
                                self.renderer._bad_line_break_count(
                                    layout.lines, request.text
                                ),
                                layout.score,
                            ),
                        )
                    )
                if pass_candidates:
                    largest = min(
                        pass_candidates,
                        key=lambda item: (
                            -item.effective_font_size,
                            item.rough_key,
                        ),
                    )
                    typography = min(
                        pass_candidates,
                        key=lambda item: item.rough_key,
                    )
                    chosen.append(largest)
                    if typography != largest:
                        chosen.append(typography)
            if chosen:
                return chosen
            fallback = self.renderer.layout_text_at_fixed_size(
                request.text,
                request.layout_rect,
                minimum,
                font_family=family,
                alignment=alignment,
                padding=padding,
                margin=margin,
                bold=bold,
                italic=italic,
            )
            fallback.is_overflow = True
            return [
                self._to_spec(
                    fallback,
                    mask_pass="overflow_fallback",
                    allow_char_break=True,
                    bold=bold,
                    italic=italic,
                    rough_key=(True, -font_pixel_size(fallback.font)),
                )
            ]

        rect = self._mask_rect(request)
        min_size = max(
            self.renderer.AUTO_READABILITY_MIN_FONT_SIZE,
            request.automatic_min_size,
        )
        max_size = self.render_service._max_font_size()
        dynamic_max = min(
            max_size,
            max(min_size, rect.height() * 0.85, rect.width() * 0.65),
        )
        sizes = self.renderer._candidate_font_sizes(min_size, dynamic_max)
        chosen: list[RoughLayoutCandidate] = []
        mask_bool = np.asarray(request.mask) > 0
        for mask_pass, inset_scale in (("mask_strict", 1.0), ("mask_relaxed", 0.7)):
            for allow_break in (False, True):
                pass_candidates: list[RoughLayoutCandidate] = []
                for size in sizes:
                    font = QFont(family)
                    _set_font_pixel_size(font, size)
                    font.setBold(bold)
                    font.setItalic(italic)
                    safe = self.renderer.make_safe_mask(
                        mask_bool,
                        padding=padding,
                        margin=margin,
                        stroke_width=max(1.0, font_pixel_size(font) / 12.0),
                        inset_scale=inset_scale,
                    )
                    for ratio in (1.12, 1.06, 1.0, 1.18):
                        layout = self.renderer._layout_text_in_mask(
                            request.text,
                            rect,
                            safe,
                            font,
                            allow_char_break=allow_break,
                            min_size=min_size,
                            line_height_ratio=ratio,
                            target_center_y=request.target_center_y,
                        )
                        if layout is None:
                            continue
                        bad = self.renderer._bad_line_break_count(layout.lines, request.text)
                        rough_key = (
                            False,
                            0.0,
                            -font_pixel_size(font),
                            bad,
                            sum(len(line.strip()) == 1 for line in layout.lines),
                            layout.score,
                            abs(ratio - 1.12),
                        )
                        pass_candidates.append(
                            self._to_spec(
                                layout,
                                mask_pass=mask_pass,
                                allow_char_break=allow_break,
                                bold=bold,
                                italic=italic,
                                rough_key=rough_key,
                            )
                        )
                if not pass_candidates:
                    continue
                largest = min(
                    pass_candidates,
                    key=lambda item: (-item.effective_font_size, item.rough_key),
                )
                typography = min(pass_candidates, key=lambda item: item.rough_key)
                chosen.append(largest)
                if typography != largest:
                    chosen.append(typography)
                else:
                    alternatives = sorted(
                        (item for item in pass_candidates if item != largest),
                        key=lambda item: (-item.effective_font_size, item.rough_key),
                    )
                    if alternatives:
                        chosen.append(alternatives[0])

        unique: dict[tuple[Any, ...], RoughLayoutCandidate] = {}
        for item in chosen:
            signature = (
                item.effective_font_size,
                item.mask_pass,
                item.allow_char_break,
                item.line_height_ratio,
                item.lines,
                tuple((slot.x, slot.y, slot.width, slot.height) for slot in item.slots),
            )
            unique.setdefault(signature, item)
        return list(unique.values())

    def _fallback_candidate(self, request: BubbleLayoutRequest) -> RoughLayoutCandidate:
        family = self._resolve_family(request)
        fallback_rect = (
            self._mask_rect(request)
            if request.mask is not None
            else request.layout_rect
        )
        fallback_size = max(
            1,
            int(
                request.bubble.font_size
                or request.automatic_min_size
            ),
        )
        layout = self.renderer.layout_text_at_fixed_size(
            request.text,
            fallback_rect,
            fallback_size,
            font_family=family,
            alignment=request.bubble.alignment or "center",
            padding=dict(request.bubble.layout_padding or {}),
            margin=dict(request.bubble.layout_margin or {}),
            target_center_y=request.target_center_y,
            bold=bool(request.bubble.bold),
            italic=bool(request.bubble.italic),
        )
        layout.is_overflow = True
        return self._to_spec(
            layout,
            mask_pass="overflow_fallback",
            allow_char_break=True,
            bold=request.bubble.bold,
            italic=request.bubble.italic,
            rough_key=(True, -font_pixel_size(layout.font)),
        )

    def _rasterize_candidate(
        self,
        worker: QtWorkerState,
        request: BubbleLayoutRequest,
        candidate: RoughLayoutCandidate,
        *,
        transient_budget: int = MAX_TRANSIENT_BYTES,
    ) -> RasterizedCandidate:
        font = QFont(candidate.font_family)
        font.setPixelSize(candidate.effective_font_size)
        font.setBold(candidate.bold)
        font.setItalic(candidate.italic)
        font.setStyleStrategy(
            QFont.StyleStrategy.PreferAntialias
            | QFont.StyleStrategy.NoSubpixelAntialias
        )
        stroke_width = max(1.0, candidate.effective_font_size / 12.0)
        pad = int(math.ceil(stroke_width)) + 4
        if not candidate.slots:
            return self._resource_failure(candidate)

        shaped: list[tuple[Any, ...]] = []
        font_identities: list[dict[str, Any]] = []
        rough_left = float("inf")
        rough_top = float("inf")
        rough_right = -float("inf")
        rough_bottom = -float("inf")
        flags = (
            QTextLayout.GlyphRunRetrievalFlag.RetrieveGlyphIndexes
            | QTextLayout.GlyphRunRetrievalFlag.RetrieveGlyphPositions
            | QTextLayout.GlyphRunRetrievalFlag.RetrieveStringIndexes
            | QTextLayout.GlyphRunRetrievalFlag.RetrieveString
        )
        for slot in candidate.slots:
            qlayout = QTextLayout(slot.text, font, worker.metric_device)
            qlayout.beginLayout()
            qline = qlayout.createLine()
            if not qline.isValid():
                qlayout.endLayout()
                continue
            qline.setLineWidth(max(1.0, slot.width))
            qlayout.endLayout()
            advance = float(qline.naturalTextWidth())
            if request.bubble.alignment == "right":
                origin_x = slot.x + max(0.0, slot.width - advance)
            elif request.bubble.alignment == "left":
                origin_x = slot.x
            else:
                origin_x = slot.x + max(0.0, (slot.width - advance) / 2.0)
            baseline_y = slot.y + float(qline.ascent())
            paint_runs = tuple(qline.glyphRuns())
            raw_identities: list[dict[str, Any]] = []
            for run in paint_runs:
                raw_font = run.rawFont()
                family_name = (
                    raw_font.familyName() or font.family()
                )
                style_name = raw_font.styleName() or ""
                head_table = bytes(raw_font.fontTable("head"))
                raw_identities.append(
                    {
                        "family": family_name,
                        "style": style_name,
                        "pixel_size": round(
                            float(raw_font.pixelSize()), 6
                        ),
                        "head_digest": hashlib.sha256(
                            head_table
                        ).hexdigest()
                        if head_table
                        else None,
                    }
                )
            metadata_runs = tuple(qline.glyphRuns(-1, -1, flags))
            starts = sorted(
                min(int(index) for index in run.stringIndexes())
                for run in metadata_runs
                if run.stringIndexes()
            )
            total_units = len(slot.text.encode("utf-16-le", errors="surrogatepass")) // 2
            run_dtos: list[CanonicalRun] = []
            for index, run in enumerate(paint_runs):
                metadata = metadata_runs[index] if index < len(metadata_runs) else None
                indexes = [int(value) for value in metadata.stringIndexes()] if metadata else []
                start = min(indexes) if indexes else 0
                end = min((value for value in starts if value > start), default=total_units)
                positions = list(run.positions())
                raw_identity = (
                    raw_identities[index]
                    if index < len(raw_identities)
                    else {
                        "family": font.family(),
                        "style": "",
                        "pixel_size": candidate.effective_font_size,
                        "head_digest": None,
                    }
                )
                run_dtos.append(
                    CanonicalRun(
                        text=_utf16_slice(slot.text, start, end),
                        origin_x=origin_x
                        + min((point.x() for point in positions), default=0.0),
                        font_family=str(raw_identity["family"]),
                        font_pixel_size=float(candidate.effective_font_size),
                        is_rtl=bool(run.isRightToLeft()),
                    )
                )
                font_identities.append(
                    {
                        **raw_identity,
                        "glyph_indexes": [int(value) for value in run.glyphIndexes()],
                        "positions": [
                            [round(point.x(), 6), round(point.y(), 6)]
                            for point in positions
                        ],
                    }
                )
            shaped.append(
                (
                    slot,
                    origin_x,
                    baseline_y,
                    advance,
                    paint_runs,
                    tuple(run_dtos),
                )
            )
            rough_left = min(rough_left, origin_x - pad)
            rough_top = min(rough_top, baseline_y - candidate.effective_font_size * 1.5 - pad)
            rough_right = max(rough_right, origin_x + advance + pad)
            rough_bottom = max(
                rough_bottom, baseline_y + candidate.effective_font_size * 0.6 + pad
            )

        if not shaped:
            return self._resource_failure(candidate)
        surface_x = int(math.floor(rough_left))
        surface_y = int(math.floor(rough_top))
        width = max(1, int(math.ceil(rough_right)) - surface_x)
        height = max(1, int(math.ceil(rough_bottom)) - surface_y)
        pixels = width * height
        # QImage, its converted RGBA buffer, line/fill/final alpha, and the
        # distance-transform scratch space coexist during rasterization.
        estimated = pixels * 16
        if (
            pixels > MAX_SURFACE_PIXELS
            or estimated > transient_budget
        ):
            return self._resource_failure(candidate)

        fill_alpha = np.zeros((height, width), dtype=np.uint8)
        public_lines: list[CanonicalShapedLine] = []
        for slot, origin_x, baseline_y, advance, paint_runs, run_dtos in shaped:
            line_image = QImage(
                width, height, QImage.Format.Format_ARGB32_Premultiplied
            )
            line_image.fill(0)
            painter = QPainter(line_image)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setPen(QColor(255, 255, 255, 255))
            base = QPointF(origin_x - surface_x, slot.y - surface_y)
            for run in paint_runs:
                painter.drawGlyphRun(base, run)
            painter.end()
            line_alpha = self._image_alpha(line_image)
            np.maximum(fill_alpha, line_alpha, out=fill_alpha)
            expanded_line = _expanded_alpha(line_alpha, stroke_width)
            ys, xs = np.where(expanded_line > 0)
            if xs.size:
                ink_left = surface_x + int(xs.min())
                ink_top = surface_y + int(ys.min())
                ink_width = int(xs.max() - xs.min() + 1)
                ink_height = int(ys.max() - ys.min() + 1)
            else:
                ink_left = int(round(origin_x))
                ink_top = int(round(baseline_y))
                ink_width = ink_height = 0
            public_lines.append(
                CanonicalShapedLine(
                    text=slot.text,
                    origin_x=round(origin_x * 64) / 64,
                    baseline_y=round(baseline_y * 64) / 64,
                    advance_width=round(advance * 64) / 64,
                    ink_left=ink_left,
                    ink_top=ink_top,
                    ink_width=ink_width,
                    ink_height=ink_height,
                    runs=run_dtos,
                )
            )

        stroke_only = _stroke_only(fill_alpha, stroke_width)
        final_alpha = compose_final_alpha(fill_alpha, stroke_only)
        total_alpha = int(final_alpha.astype(np.uint64).sum())
        outside_sum, outside_visible = self._outside_alpha(
            request,
            candidate,
            final_alpha,
            surface_x,
            surface_y,
        )
        outside_ratio = outside_sum / max(1, total_alpha)
        visible_count = int(np.count_nonzero(final_alpha > 8))
        visible_y, visible_x = np.where(final_alpha > 0)
        page_safe = bool(visible_x.size) and (
            surface_x + int(visible_x.min()) >= 0
            and surface_y + int(visible_y.min()) >= 0
            and surface_x + int(visible_x.max()) + 1 <= request.page_width
            and surface_y + int(visible_y.max()) + 1 <= request.page_height
        )
        raster_safe = (
            page_safe
            and total_alpha > 0
            and outside_ratio <= 0.002
            and outside_visible <= max(2, int(visible_count * 0.001))
        )
        fill_alpha = np.array(fill_alpha, dtype=np.uint8, order="C", copy=True)
        stroke_only = np.array(stroke_only, dtype=np.uint8, order="C", copy=True)
        fill_alpha.flags.writeable = False
        stroke_only.flags.writeable = False
        assert fill_alpha.base is None and stroke_only.base is None
        return RasterizedCandidate(
            candidate=candidate,
            fill_alpha=fill_alpha,
            stroke_only_alpha=stroke_only,
            surface_x=surface_x,
            surface_y=surface_y,
            shaped_lines=tuple(public_lines),
            font_identities=tuple(font_identities),
            diagnostics=CandidateDiagnostics(
                effective_font_size=candidate.effective_font_size,
                mask_pass=candidate.mask_pass,
                allow_char_break=candidate.allow_char_break,
                raster_safe=raster_safe,
                outside_alpha_ratio=float(outside_ratio),
                outside_visible_pixels=outside_visible,
            ),
        )

    @staticmethod
    def _image_alpha(image: QImage) -> np.ndarray:
        converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
        view = np.frombuffer(
            converted.bits(), dtype=np.uint8, count=converted.sizeInBytes()
        )
        rows = view.reshape(converted.height(), converted.bytesPerLine())
        return (
            rows[:, : converted.width() * 4]
            .reshape(converted.height(), converted.width(), 4)[:, :, 3]
            .copy()
        )

    def _outside_alpha(
        self,
        request: BubbleLayoutRequest,
        candidate: RoughLayoutCandidate,
        alpha: np.ndarray,
        surface_x: int,
        surface_y: int,
    ) -> tuple[int, int]:
        if request.mask is None or candidate.mask_pass in {"rect", "fixed", "overflow_fallback"}:
            return 0, 0
        scale = 1.0 if candidate.mask_pass == "mask_strict" else 0.7
        safe = self.renderer.make_safe_mask(
            np.asarray(request.mask) > 0,
            padding=dict(request.bubble.layout_padding or {}),
            margin=dict(request.bubble.layout_margin or {}),
            stroke_width=max(1.0, candidate.effective_font_size / 12.0),
            inset_scale=scale,
        )
        allowed = np.zeros_like(alpha, dtype=bool)
        bx = (
            request.mask_bounds[0]
            if request.mask_bounds is not None
            else int(round(request.bubble.box.x))
        )
        by = (
            request.mask_bounds[1]
            if request.mask_bounds is not None
            else int(round(request.bubble.box.y))
        )
        x1 = max(0, bx - surface_x)
        y1 = max(0, by - surface_y)
        x2 = min(alpha.shape[1], bx - surface_x + safe.shape[1])
        y2 = min(alpha.shape[0], by - surface_y + safe.shape[0])
        if x2 > x1 and y2 > y1:
            sx1 = max(0, surface_x - bx)
            sy1 = max(0, surface_y - by)
            sx2 = sx1 + (x2 - x1)
            sy2 = sy1 + (y2 - y1)
            allowed[y1:y2, x1:x2] = safe[sy1:sy2, sx1:sx2]
        outside = alpha[~allowed]
        return int(outside.astype(np.uint64).sum()), int(np.count_nonzero(outside > 8))

    @staticmethod
    def _resource_failure(candidate: RoughLayoutCandidate) -> RasterizedCandidate:
        empty = np.zeros((1, 1), dtype=np.uint8)
        empty.flags.writeable = False
        return RasterizedCandidate(
            candidate=candidate,
            fill_alpha=empty,
            stroke_only_alpha=empty,
            surface_x=0,
            surface_y=0,
            shaped_lines=(),
            font_identities=(),
            diagnostics=CandidateDiagnostics(
                effective_font_size=candidate.effective_font_size,
                mask_pass=candidate.mask_pass,
                allow_char_break=candidate.allow_char_break,
                raster_safe=False,
                outside_alpha_ratio=1.0,
                outside_visible_pixels=0,
                resource_violation=True,
            ),
        )

    def _final_key(self, candidate: RasterizedCandidate) -> tuple[Any, ...]:
        spec = candidate.candidate
        orphan = sum(len(line.strip()) == 1 for line in spec.lines)
        return (
            spec.rough_key[3] if len(spec.rough_key) > 3 else 0,
            orphan,
            0 if spec.mask_pass == "mask_strict" else 1,
            0 if not spec.allow_char_break else 1,
            spec.score,
            abs(spec.area_usage - 0.62),
            abs(spec.line_height_ratio - 1.12),
        )

    def _freeze_artifact(
        self,
        request: BubbleLayoutRequest,
        selected: RasterizedCandidate,
        candidates: list[RoughLayoutCandidate],
        raster_diagnostics: list[CandidateDiagnostics],
        fmax: int,
        strict_max: int | None,
        relaxed_max: int | None,
    ) -> CanonicalLayoutArtifact:
        spec = selected.candidate
        public_lines: tuple[CanonicalPublicLine, ...]
        if selected.shaped_lines:
            public_lines = tuple(
                CanonicalPublicLine(
                    text=line.text,
                    x=float(line.ink_left),
                    y=float(line.ink_top),
                    width=float(line.ink_width),
                    height=float(line.ink_height),
                    origin_x=line.origin_x,
                    baseline_y=line.baseline_y,
                    advance_width=line.advance_width,
                    ink_left=line.ink_left,
                    ink_top=line.ink_top,
                    ink_width=line.ink_width,
                    ink_height=line.ink_height,
                    runs=line.runs,
                )
                for line in selected.shaped_lines
            )
        else:
            public_lines = tuple(spec.slots)
        public_layout = PublicTextLayoutResult(
            font=FontDescriptor(
                spec.font_family,
                spec.effective_font_size,
                spec.bold,
                spec.italic,
            ),
            lines=tuple(spec.lines),  # type: ignore[arg-type]
            render_width=max(
                (
                    line.advance_width
                    if line.advance_width is not None
                    else line.width
                    for line in public_lines
                ),
                default=0.0,
            ),
            line_layouts=public_lines,  # type: ignore[arg-type]
            score=spec.score,
            is_overflow=spec.is_overflow or not selected.diagnostics.raster_safe,
            reached_min_font=spec.reached_min_font,
            line_height_ratio=spec.line_height_ratio,
            area_usage=spec.area_usage,
        )
        alpha_digest = hashlib.sha256(
            selected.fill_alpha.tobytes() + selected.stroke_only_alpha.tobytes()
        ).hexdigest()
        serialized_lines = [
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
        fingerprint = canonical_hash(
            {
                "input_key": request.input_key,
                "font_identities": selected.font_identities,
                "lines": serialized_lines,
                "alpha_digest": alpha_digest,
            }
        )
        pass_name = spec.mask_pass
        safe_area_ratio = 1.0
        if (
            request.mask is not None
            and pass_name in {"mask_strict", "mask_relaxed"}
        ):
            safe_mask = self.renderer.make_safe_mask(
                np.asarray(request.mask) > 0,
                padding=dict(
                    request.bubble.layout_padding or {}
                ),
                margin=dict(
                    request.bubble.layout_margin or {}
                ),
                stroke_width=max(
                    1.0, spec.effective_font_size / 12.0
                ),
                inset_scale=1.0
                if pass_name == "mask_strict"
                else 0.7,
            )
            safe_area_ratio = float(
                np.count_nonzero(safe_mask)
            ) / max(1, int(np.count_nonzero(request.mask)))
        diagnostics = {
            "selected_pass": pass_name,
            "selected_font_size": spec.effective_font_size,
            "largest_feasible_font_size": fmax,
            "strict_max_font_size": strict_max,
            "relaxed_max_font_size": relaxed_max,
            "allow_char_break": spec.allow_char_break,
            "candidate_count": len(candidates),
            "rasterized_candidate_count": len(raster_diagnostics),
            "safe_area_ratio": round(safe_area_ratio, 6),
            "body_mask_source": request.mask_source,
            "outside_alpha_ratio": selected.diagnostics.outside_alpha_ratio,
            "resource_violation_count": sum(
                item.resource_violation for item in raster_diagnostics
            ),
            "error_code": (
                "CANONICAL_LAYOUT_RESOURCE_EXHAUSTED"
                if selected.diagnostics.resource_violation
                else None
            ),
        }
        public_layout = replace(
            public_layout,
            diagnostics=dict(diagnostics),
        )
        return CanonicalLayoutArtifact(
            selected=selected,
            public_layout=public_layout,
            layout_fingerprint=fingerprint,
            font_identities=selected.font_identities,
            diagnostics=diagnostics,
            page_width=request.page_width,
            page_height=request.page_height,
        )
