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

import pipeline.auto_typeset as pipeline_module
from app.models import MangaPage, TextBubble
from domain.project_state import ProjectState
from modules.config import AppConfig
from services.job_service import job_manager
from services.bubble_analysis_service import BubbleAnalysisResult, BubbleData
from services.layout_planner_service import Insets


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
        self.state = ProjectState()
        self.config = AppConfig()

    def tearDown(self):
        pass

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
        with self.state.lock:
            self.state.pages = [page]
            self.state.current_page_idx = 0
            self.state.revision = 0

        inpainting_service = FakeInpaintingService()
        translation_service = FakeTranslationService()

        with (
            patch.object(pipeline_module, "ensure_page_image", lambda page: None),
            patch.object(pipeline_module, "encode_preview_jpeg_bytes", lambda image: b"preview"),
            patch.object(pipeline_module, "encode_thumbnail_bytes", lambda image: b"thumb"),
        ):
            result = pipeline_module.AutoTypesetPipeline(
                state=self.state,
                config=self.config,
                job_manager=job_manager,
                detection_service=SimpleNamespace(),
                inpainting_service=inpainting_service,
                translation_service=translation_service,
            ).run_page(
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

    def test_run_page_records_stage_provenance(self):
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
        with self.state.lock:
            self.state.pages = [page]
            self.state.current_page_idx = 0
            self.state.revision = 0

        pipeline = pipeline_module.AutoTypesetPipeline(
            state=self.state,
            config=self.config,
            job_manager=job_manager,
            detection_service=SimpleNamespace(),
            inpainting_service=FakeInpaintingService(),
            translation_service=FakeTranslationService(),
        )

        with (
            patch.object(pipeline_module, "ensure_page_image", lambda page: None),
            patch.object(pipeline_module, "encode_preview_jpeg_bytes", lambda image: b"preview"),
            patch.object(pipeline_module, "encode_thumbnail_bytes", lambda image: b"thumb"),
        ):
            pipeline.run_page({"cancel_requested": False}, "page_a", show_progress=False)

        assert pipeline.last_result is not None
        assert [stage.stage for stage in pipeline.last_result.context.provenance.stages] == [
            "load_page",
            "detect_analyze",
            "inpaint_translate",
            "commit_page",
        ]

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
                config=self.config,
                page_analysis_service=pipeline_module.page_analysis_service,
                bubble_analysis_service=pipeline_module.bubble_analysis_service,
                layout_planner_service=pipeline_module.layout_planner_service,
            )

        self.assertEqual(len(bubbles), 1)
        self.assertEqual(bubbles[0].color, "#0c2238")

    def test_bubbles_from_analysis_preserves_layout_box(self):
        image = np.zeros((40, 40, 3), dtype=np.uint8)
        bubble_data = BubbleData(
            bubble_box=(2, 3, 30, 31),
            text_box=(4, 5, 28, 29),
            layout_box=(8, 9, 24, 25),
            text="hello",
            text_class="text_bubble",
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
                config=self.config,
                page_analysis_service=pipeline_module.page_analysis_service,
                bubble_analysis_service=pipeline_module.bubble_analysis_service,
                layout_planner_service=pipeline_module.layout_planner_service,
            )

        self.assertEqual(len(bubbles), 1)
        self.assertIsNotNone(bubbles[0].layout_box)
        self.assertEqual(bubbles[0].layout_box, QRectF(8, 9, 16, 16))

    def test_bubbles_from_analysis_leaves_font_family_on_auto(self):
        image = np.zeros((40, 40, 3), dtype=np.uint8)
        bubble_data = BubbleData(
            bubble_box=(2, 3, 30, 31),
            text_box=(4, 5, 28, 29),
            layout_box=(8, 9, 24, 25),
            text="hello",
            text_class="text_bubble",
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
                config=self.config,
                page_analysis_service=pipeline_module.page_analysis_service,
                bubble_analysis_service=pipeline_module.bubble_analysis_service,
                layout_planner_service=pipeline_module.layout_planner_service,
            )

        self.assertEqual(len(bubbles), 1)
        self.assertEqual(bubbles[0].font_family, "")

    def test_bubbles_from_analysis_preserves_layout_plan_metadata(self):
        image = np.zeros((40, 40, 3), dtype=np.uint8)
        bubble_data = BubbleData(
            bubble_box=(2, 3, 30, 31),
            text_box=(4, 5, 28, 29),
            layout_box=(8, 9, 24, 25),
            text="hello",
            text_class="text_bubble",
        )

        with (
            patch.object(
                pipeline_module.page_analysis_service,
                "analyze",
                return_value=SimpleNamespace(
                    reading_order=SimpleNamespace(direction="rtl"),
                    writing_mode="vertical",
                ),
            ),
            patch.object(
                pipeline_module.bubble_analysis_service,
                "analyze",
                return_value=BubbleAnalysisResult(
                    bubbles=[bubble_data],
                    reading_order="RTL",
                    writing_mode="vertical",
                ),
            ),
            patch.object(
                pipeline_module.layout_planner_service,
                "plan",
                return_value=SimpleNamespace(
                    alignment="right",
                    writing_mode="vertical",
                    text_direction="rtl",
                    justification="full",
                    padding=Insets(top=1, right=2, bottom=3, left=4),
                    margin=Insets(top=5, right=6, bottom=7, left=8),
                    confidence=0.73,
                    reasoning="writing_mode=vertical; alignment=right",
                ),
            ),
        ):
            bubbles = pipeline_module._bubbles_from_analysis(
                image,
                blocks=[],
                source_lang="Japanese",
                target_lang="Korean",
                config=self.config,
                page_analysis_service=pipeline_module.page_analysis_service,
                bubble_analysis_service=pipeline_module.bubble_analysis_service,
                layout_planner_service=pipeline_module.layout_planner_service,
            )

        self.assertEqual(len(bubbles), 1)
        bubble = bubbles[0]
        self.assertEqual(bubble.alignment, "right")
        self.assertEqual(bubble.writing_mode, "vertical")
        self.assertEqual(bubble.text_direction, "rtl")
        self.assertEqual(bubble.justification, "full")
        self.assertEqual(bubble.layout_padding, {"top": 1, "right": 2, "bottom": 3, "left": 4})
        self.assertEqual(bubble.layout_margin, {"top": 5, "right": 6, "bottom": 7, "left": 8})
        self.assertEqual(bubble.layout_confidence, 0.73)
        self.assertEqual(bubble.layout_reasoning, "writing_mode=vertical; alignment=right")

    def test_merge_overlapping_bubbles_preserves_cjk_lines_without_spaces(self):
        first = TextBubble(
            id=1,
            box=QRectF(10, 10, 30, 30),
            text_box=QRectF(12, 12, 10, 10),
            text="こん",
            translated="안녕",
        )
        second = TextBubble(
            id=2,
            box=QRectF(12, 12, 30, 30),
            text_box=QRectF(20, 20, 10, 10),
            text="にちは",
            translated="하세요",
        )

        merged = pipeline_module._merge_overlapping_bubbles([first, second])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].text, "こん\nにちは")
        self.assertEqual(merged[0].translated, "안녕\n하세요")


if __name__ == "__main__":
    unittest.main()
