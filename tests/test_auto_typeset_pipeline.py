import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QRectF

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import services.auto_typeset_pipeline as pipeline_module
from app.models import MangaPage, TextBubble
from services.bubble_analysis_service import BubbleAnalysisResult, BubbleData


class FakeInpaintingService:
    def __init__(self):
        self.calls = []

    def clean_background(self, image, boxes, bubble_boxes, protect_edges=True):
        self.calls.append(
            {
                "boxes": boxes,
                "bubble_boxes": bubble_boxes,
                "protect_edges": protect_edges,
            }
        )
        cleaned = image.copy()
        cleaned[:, :] = 255
        return cleaned


class FakeTranslationService:
    def __init__(self):
        self.calls = []

    def translate_blocks(self, blocks, src_lang, tgt_lang, cv_image):
        self.calls.append(
            {
                "texts": [block.text for block in blocks],
                "src_lang": src_lang,
                "tgt_lang": tgt_lang,
                "shape": cv_image.shape,
            }
        )
        for block in blocks:
            block.translation = f"translated:{block.text}"


class AutoTypesetPipelineTests(unittest.TestCase):
    def setUp(self):
        self.original_pages = list(pipeline_module.state.pages)
        self.original_revision = pipeline_module.state.revision
        self.original_current_page_idx = pipeline_module.state.current_page_idx

    def tearDown(self):
        with pipeline_module.state.lock:
            pipeline_module.state.pages = self.original_pages
            pipeline_module.state.revision = self.original_revision
            pipeline_module.state.current_page_idx = self.original_current_page_idx

    def test_run_page_translates_existing_bubbles_and_updates_page_state(self):
        page = MangaPage(
            file_path="sample.png",
            cv_image=np.zeros((24, 32, 3), dtype=np.uint8),
            bubbles=[
                TextBubble(
                    id=1,
                    box=QRectF(2, 3, 10, 8),
                    text_box=QRectF(3, 4, 8, 6),
                    text="hello",
                    translated="",
                )
            ],
            bubble_counter=1,
        )
        page.page_id = "page_a"
        with pipeline_module.state.lock:
            pipeline_module.state.pages = [page]
            pipeline_module.state.current_page_idx = 0
            pipeline_module.state.revision = 0

        inpainting_service = FakeInpaintingService()
        translation_service = FakeTranslationService()

        with (
            patch.object(pipeline_module, "ensure_page_image", lambda page: None),
            patch.object(pipeline_module, "inpainting_service", inpainting_service),
            patch.object(pipeline_module, "translation_service", translation_service),
            patch.object(pipeline_module, "encode_preview_jpeg_bytes", lambda image: b"preview"),
            patch.object(pipeline_module, "encode_thumbnail_bytes", lambda image: b"thumb"),
        ):
            result = pipeline_module.AutoTypesetPipeline().run_page(
                {"cancel_requested": False},
                "page_a",
                show_progress=True,
            )

        self.assertEqual(result, {"translated_count": 1})
        self.assertEqual(page.bubbles[0].translated, "translated:hello")
        self.assertEqual(page.status, "ready_for_review")
        self.assertEqual(page._preview_inpainted_bytes, b"preview")
        self.assertEqual(page._thumbnail_original_bytes, b"thumb")
        self.assertIsNotNone(page.inpainted_image)
        self.assertEqual(translation_service.calls[0]["texts"], ["hello"])
        self.assertEqual(inpainting_service.calls[0]["boxes"], [[3.0, 4.0, 11.0, 10.0]])
        self.assertEqual(inpainting_service.calls[0]["bubble_boxes"], [[2.0, 3.0, 12.0, 11.0]])

    def test_bubbles_from_analysis_preserves_detected_font_color(self):
        image = np.zeros((40, 40, 3), dtype=np.uint8)
        bubble_data = BubbleData(
            bubble_box=(2, 3, 20, 21),
            text_box=(4, 5, 18, 19),
            layout_box=(5, 6, 17, 18),
            text="hello",
            text_class="text_bubble",
            font_color=(12, 34, 56),
        )

        with (
            patch.object(
                pipeline_module.page_analysis_service,
                "analyze",
                return_value=SimpleNamespace(
                    reading_order=SimpleNamespace(direction="ltr"),
                    writing_mode="horizontal",
                ),
            ),
            patch.object(
                pipeline_module.bubble_analysis_service,
                "analyze",
                return_value=BubbleAnalysisResult(
                    bubbles=[bubble_data],
                    reading_order="LTR",
                    writing_mode="horizontal",
                ),
            ),
            patch.object(
                pipeline_module.layout_planner_service,
                "plan",
                return_value=SimpleNamespace(alignment="center"),
            ),
        ):
            bubbles = pipeline_module._bubbles_from_analysis(
                image,
                blocks=[],
                source_lang="Japanese",
                target_lang="Korean",
            )

        self.assertEqual(len(bubbles), 1)
        self.assertEqual(bubbles[0].color, "#0c2238")


if __name__ == "__main__":
    unittest.main()
