import os
import logging
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColorSpace, QImage, QPainter
from typing import Optional, Any, Callable
from ...core.models import MangaPage
from .service import RenderService
from .renderer import font_pixel_size

logger = logging.getLogger(__name__)

FontResolver = Callable[[str | None], str | None]


@lru_cache(maxsize=64)
def resolve_font_path(font_family: str | None) -> str | None:
    from ...infrastructure.fonts import resolver as font_resolver

    resolved, _chain = font_resolver.resolve(
        text="",
        requested_family=font_family,
        target_lang="Korean",
    )
    return resolved.path


class ExportService:
    def __init__(self, render_service: Optional[RenderService] = None, text_layer_service=None) -> None:
        self.render_service: RenderService = render_service or RenderService()
        self.text_layer_service = text_layer_service

    def render_page(
        self,
        page: MangaPage,
        font_path: str | None,
        font_family: str | None = None,
        font_resolver: FontResolver | None = None,
    ) -> Optional[Image.Image]:
        """Compose the exact cached Qt text tiles onto the inpainted page."""
        if self.text_layer_service is not None:
            return self._render_page_from_tiles(page)
        # Compatibility path for isolated unit tests that construct the export
        # service without the application composition root.
        return self._render_page_legacy(page, font_path, font_family, font_resolver)

    def _render_page_from_tiles(self, page: MangaPage) -> Image.Image | None:
        if page.inpainted_image is None:
            return None
        tiles = []
        failures = []
        for bubble in page.bubbles:
            if not (bubble.translated or "").strip():
                continue
            try:
                tiles.append(self.text_layer_service.create_tile(
                    page.page_id,
                    bubble,
                    page.cv_image,
                    image_revision=page.image_visual_revision,
                ))
            except Exception:
                logger.exception("Canonical export tile failed. bubble_id=%s", bubble.id)
                failures.append(bubble.id)
        if failures:
            raise RuntimeError(f"TEXT_LAYER_EXPORT_FAILED:{','.join(map(str, failures))}")

        def composite(_worker):
            bgr = np.ascontiguousarray(page.inpainted_image)
            rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
            height, width = rgba.shape[:2]
            canvas = QImage(rgba.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
            canvas.setDevicePixelRatio(1.0)
            canvas.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
            painter = QPainter(canvas)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            for tile in tiles:
                tile_image = QImage.fromData(tile.png_bytes, "PNG")
                if tile_image.isNull():
                    painter.end()
                    raise RuntimeError(f"TEXT_LAYER_EXPORT_FAILED:{tile.bubble_id}")
                painter.drawImage(QPoint(tile.crop_x, tile.crop_y), tile_image)
            painter.end()
            converted = canvas.convertToFormat(QImage.Format.Format_RGBA8888)
            view = np.frombuffer(converted.bits(), dtype=np.uint8, count=converted.sizeInBytes())
            rows = view.reshape(height, converted.bytesPerLine())
            output = rows[:, :width * 4].reshape(height, width, 4).copy()
            return output

        rgba = self.text_layer_service.executor.run(composite)
        return Image.fromarray(rgba, mode="RGBA")

    def _render_page_legacy(
        self,
        page: MangaPage,
        font_path: str | None,
        font_family: str | None,
        font_resolver: FontResolver | None,
    ) -> Optional[Image.Image]:
        if font_path is None and font_family is not None:
            font_path = resolve_font_path(font_family)
        if font_resolver is None:
            font_resolver = resolve_font_path
        if page.inpainted_image is None:
            return None

        cv_img = page.inpainted_image.copy()
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        draw = ImageDraw.Draw(pil_image)

        default_font_path = font_path or self._system_fallback_font_path()
        ttfont = self._load_font(default_font_path, 20)
        if ttfont is None:
            logger.warning("Fallback font used for export default font. requested=%s", default_font_path)
            ttfont = ImageFont.load_default()

        for b in page.bubbles:
            if not b.translated:
                continue
            rect = b.box
            x1, y1 = int(rect.x), int(rect.y)
            rh = int(rect.height)
            text = b.translated
            bubble_font_family = b.font_family or font_family
            bubble_font_path = font_resolver(bubble_font_family) if font_resolver else default_font_path
            bubble_font_path = bubble_font_path or default_font_path

            layout = self.render_service.get_layout_for_bubble(
                text, b, image=page.cv_image, font_family=bubble_font_family
            )
            font = layout.font
            # Layout is the single source of truth for line positions and
            # glyph size in both automatic and fixed modes.
            font_size = font_pixel_size(font)
            if font_size <= 0:
                font_size = 12

            if bubble_font_path:
                pil_font = self._load_font(bubble_font_path, font_size)
                if pil_font is None:
                    logger.warning(
                        "Fallback font used for bubble export. bubble_id=%s requested=%s", b.id, bubble_font_path
                    )
                    pil_font = ttfont
            else:
                logger.warning("Fallback font used for bubble export. bubble_id=%s requested=None", b.id)
                pil_font = ttfont

            fallback_line_h = int(font_size * 1.2) + 2
            for i, line_layout in enumerate(layout.line_layouts):
                line = line_layout.text
                bbox = draw.textbbox((0, 0), line, font=pil_font)
                tw = int(bbox[2] - bbox[0])
                if b.alignment == "left":
                    lx = int(line_layout.x)
                elif b.alignment == "right":
                    lx = int(line_layout.x + max(0, line_layout.width - tw))
                else:
                    lx = int(line_layout.x + max(0, (line_layout.width - tw) / 2))
                ly = int(line_layout.y)
                self._draw_text(pil_image, (lx, ly), line, pil_font, self._hex_to_rgb(b.color, b.id), b.bold, b.italic)

            if not layout.line_layouts:
                ly = y1 + max(0, (rh - fallback_line_h) // 2)
                self._draw_text(
                    pil_image, (x1 + 4, ly), text, pil_font, self._hex_to_rgb(b.color, b.id), b.bold, b.italic
                )

        return pil_image

    def _system_fallback_font_path(self) -> str | None:
        import platform
        system = platform.system()

        if system == "Windows":
            fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
            for filename in ("malgun.ttf", "gulim.ttc", "arial.ttf"):
                path = os.path.join(fonts_dir, filename)
                if os.path.exists(path):
                    return path
        elif system == "Darwin":
            for path in (
                "/System/Library/Fonts/AppleGothic.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
            ):
                if os.path.exists(path):
                    return path
        else:  # Linux
            for path in (
                "/usr/share/fonts/truetype/nanum/NanumGothic-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ):
                if os.path.exists(path):
                    return path
        return None

    def _load_font(self, font_path: str | None, font_size: int) -> Any | None:
        if not font_path:
            return None
        try:
            return ImageFont.truetype(font_path, font_size)
        except Exception:
            logger.exception("Failed to load font from %s", font_path)
            return None

    def _hex_to_rgb(self, color: str, bubble_id: int | None = None) -> tuple[int, int, int]:
        normalized = color.strip().lstrip("#")
        if len(normalized) != 6:
            logger.warning("Invalid export color; using black fallback. bubble_id=%s color=%s", bubble_id, color)
            return (0, 0, 0)
        try:
            return (
                int(normalized[0:2], 16),
                int(normalized[2:4], 16),
                int(normalized[4:6], 16),
            )
        except ValueError:
            logger.warning("Invalid export color; using black fallback. bubble_id=%s color=%s", bubble_id, color)
            return (0, 0, 0)

    def _draw_text(
        self,
        image: Image.Image,
        position: tuple[int, int],
        text: str,
        font: Any,
        fill: tuple[int, int, int],
        bold: bool,
        italic: bool,
    ) -> None:
        # Calculate stroke/outline parameters dynamically for readability
        luminance = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
        stroke_fill = (255, 255, 255) if luminance < 128 else (0, 0, 0)
        font_size = getattr(font, "size", 12)
        stroke_width = max(1, font_size // 12)

        if not italic:
            draw = ImageDraw.Draw(image)
            draw.text(position, text, fill=fill, font=font, stroke_width=stroke_width, stroke_fill=stroke_fill)
            if bold:
                draw.text((position[0] + 1, position[1]), text, fill=fill, font=font, stroke_width=stroke_width, stroke_fill=stroke_fill)
            return

        measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = measure.textbbox((0, 0), text, font=font)
        text_width = max(1, int(bbox[2] - bbox[0]))
        text_height = max(1, int(bbox[3] - bbox[1]))
        slant = max(2, text_height // 4)
        layer = Image.new("RGBA", (text_width + slant + 4, text_height + 4), (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        origin = (1, int(1 - bbox[1]))
        layer_draw.text(origin, text, fill=fill + (255,), font=font, stroke_width=stroke_width, stroke_fill=stroke_fill + (255,))
        if bold:
            layer_draw.text((origin[0] + 1, origin[1]), text, fill=fill + (255,), font=font, stroke_width=stroke_width, stroke_fill=stroke_fill + (255,))

        skewed = layer.transform(
            (layer.width + slant, layer.height),
            Image.Transform.AFFINE,
            (1, -0.22, slant, 0, 1, 0),
            resample=Image.Resampling.BICUBIC,
        )
        image.paste(skewed, position, skewed)
