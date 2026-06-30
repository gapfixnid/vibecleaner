import os
import logging
import cv2
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtGui import QFontMetricsF
from typing import Optional, Any, Callable
from app.models import MangaPage
from services.render_service import RenderService

logger = logging.getLogger(__name__)

FontResolver = Callable[[str | None], str | None]


class ExportService:
    def __init__(self, render_service: Optional[RenderService] = None) -> None:
        self.render_service: RenderService = render_service or RenderService()

    def render_page(
        self,
        page: MangaPage,
        font_path: str | None,
        font_family: str | None = None,
        font_resolver: FontResolver | None = None,
    ) -> Optional[Image.Image]:
        """Render a single page's export image using Pillow."""
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
            x1, y1 = int(rect.x()), int(rect.y())
            rh = int(rect.height())
            text = b.translated
            bubble_font_family = b.font_family or font_family
            bubble_font_path = font_resolver(bubble_font_family) if font_resolver else default_font_path
            bubble_font_path = bubble_font_path or default_font_path

            layout = self.render_service.get_layout_for_bubble(
                text, b, image=page.cv_image, font_family=bubble_font_family
            )
            font = layout.font
            font_size = b.font_size if b.font_size > 0 else int(font.pointSizeF())
            if font_size <= 0:
                font_size = 12
            font.setPointSize(font_size)
            font.setBold(b.bold)
            font.setItalic(b.italic)

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

            metrics = QFontMetricsF(font)
            fallback_line_h = int(metrics.height()) + 2
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
