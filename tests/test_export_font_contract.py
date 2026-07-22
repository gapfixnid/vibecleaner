import os
from types import SimpleNamespace

import numpy as np
from PIL import ImageFont

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from backend.core.models import MangaPage, Rect, TextBubble
from backend.engines.rendering.export import ExportService
from backend.engines.rendering.renderer import TextLineLayout


def test_export_uses_layout_computed_size_instead_of_raw_manual_size():
    app = QApplication.instance() or QApplication([])
    assert app is not None

    layout_font = QFont("Arial")
    layout_font.setPixelSize(18)
    layout = SimpleNamespace(
        font=layout_font,
        line_layouts=[TextLineLayout("translated", 4, 4, 92, 22)],
    )
    render_service = SimpleNamespace(get_layout_for_bubble=lambda *args, **kwargs: layout)
    export_service = ExportService(render_service=render_service)
    loaded_sizes: list[int] = []

    def load_font(_path, size):
        loaded_sizes.append(size)
        return ImageFont.load_default()

    export_service._load_font = load_font
    page = MangaPage(
        file_path="sample.png",
        cv_image=np.zeros((80, 100, 3), dtype=np.uint8),
        inpainted_image=np.zeros((80, 100, 3), dtype=np.uint8),
        bubbles=[
            TextBubble(
                id=1,
                box=Rect(0, 0, 100, 80),
                translated="translated",
                font_family="Arial",
                font_size=28,
            )
        ],
    )

    rendered = export_service.render_page(
        page,
        font_path="fake.ttf",
        font_resolver=lambda _family: "fake.ttf",
    )

    assert rendered is not None
    assert 18 in loaded_sizes
    assert 28 not in loaded_sizes
