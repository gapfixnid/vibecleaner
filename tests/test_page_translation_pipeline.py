from core.config import AppConfigSnapshot
from core.models.geometry import Box
from core.models.image import ImageData
from core.models.page import MangaPage
from core.models.text import TextRegion
from core.ports.detection import DetectionResult
from core.ports.inpainting import InpaintResult
from core.ports.ocr import OcrResult
from core.ports.rendering import RenderResult
from core.ports.translation import TranslationResult
from pipeline.context import PipelineContext
from pipeline.planner import PipelinePlanner
from pipeline.registry import StageRegistry
from pipeline.runner import PipelineRunner
from pipeline.stages.detection import DetectionStage
from pipeline.stages.inpainting import InpaintingStage
from pipeline.stages.layout import LayoutStage
from pipeline.stages.ocr import OcrStage
from pipeline.stages.rendering import RenderingStage
from pipeline.stages.translation import TranslationStage
from pipeline.strategies.engine_selection import EngineSelectionStrategy


class FakeDetector:
    def detect(self, image, options):
        return DetectionResult(regions=[TextRegion(box=Box(1, 2, 11, 12))], engine="fake-detector")


class FakeOcr:
    def recognize(self, image, regions, options):
        return OcrResult(regions=[TextRegion(box=regions[0].box, text="hello")], engine="fake-ocr")


class FakeTranslator:
    def translate_batch(self, items, options):
        return TranslationResult(translations={items[0].id: "안녕"}, engine="fake-translator")


class FakeInpainter:
    def inpaint(self, image, regions, options):
        return InpaintResult(image=image, engine="fake-inpainter")


class FakeRenderer:
    def render(self, image, bubbles, options):
        return RenderResult(image=image, engine="fake-renderer")


def make_runner():
    strategy = EngineSelectionStrategy()
    registry = StageRegistry()
    registry.register(DetectionStage(FakeDetector(), strategy))
    registry.register(OcrStage(FakeOcr(), strategy))
    registry.register(TranslationStage(FakeTranslator(), strategy))
    registry.register(InpaintingStage(FakeInpainter(), strategy))
    registry.register(LayoutStage())
    registry.register(RenderingStage(FakeRenderer(), strategy))
    return PipelineRunner(registry)


def test_translate_page_pipeline_runs_all_stages():
    context = PipelineContext(
        page_id="page-1",
        page=MangaPage(file_path="C:/tmp/page.png", page_id="page-1"),
        image=ImageData(array=object(), explicit_width=100, explicit_height=100),
        settings=AppConfigSnapshot(target_language="Korean"),
    )

    result = make_runner().run(context, PipelinePlanner().translate_page_plan())

    assert result.succeeded
    assert "detection_result" in result.context.artifacts
    assert "ocr_result" in result.context.artifacts
    assert "translation_result" in result.context.artifacts
    assert "inpaint_result" in result.context.artifacts
    assert "layout_result" in result.context.artifacts
    assert "render_result" in result.context.artifacts
    assert result.context.page.bubbles[0].translated == "안녕"
