from core.models.geometry import Box
from core.models.image import ImageData
from core.models.page import Bubble
from core.models.text import TextRegion
from core.ports.detection import DetectionOptions
from core.ports.inpainting import InpaintOptions, InpaintRegion
from core.ports.ocr import OcrOptions
from core.ports.rendering import RenderOptions
from core.ports.translation import TranslationInput, TranslationOptions
from engines.detection.adapter import DetectionEngineAdapter
from engines.inpainting.adapter import InpaintingEngineAdapter
from engines.ocr.adapter import OcrEngineAdapter
from engines.rendering.adapter import RenderingEngineAdapter
from engines.translation.adapter import TranslationEngineAdapter


class FakeLegacyBlock:
    def __init__(self, xyxy, text=""):
        self.xyxy = xyxy
        self.text = text
        self.translation = ""


class FakeLegacyDetector:
    def detect(self, image):
        return [FakeLegacyBlock([1, 2, 11, 12])]


class FakeLegacyOcr:
    def recognize(self, image, regions, options):
        return ["こんにちは"]


class FakeLegacyTranslator:
    def translate(self, text, source_language, target_language):
        return f"{text}:{target_language}"


class FakeLegacyInpainter:
    def inpaint(self, image, boxes, bubble_boxes=None, protect_edges=False):
        return image


class FakeLegacyRenderer:
    def render(self, image, bubbles, options):
        return image


def test_detection_adapter_converts_legacy_blocks_to_regions():
    adapter = DetectionEngineAdapter(engine=FakeLegacyDetector())
    image = ImageData(array=None, explicit_width=100, explicit_height=100, mode="RGB")

    result = adapter.detect(image, DetectionOptions())

    assert result.regions[0].box == Box(x1=1, y1=2, x2=11, y2=12)


def test_ocr_adapter_adds_recognized_text_to_regions():
    adapter = OcrEngineAdapter(engine=FakeLegacyOcr())
    region = TextRegion(box=Box(1, 2, 11, 12))

    result = adapter.recognize(ImageData(array=None), [region], OcrOptions())

    assert result.regions[0].text == "こんにちは"


def test_translation_adapter_returns_translation_map():
    adapter = TranslationEngineAdapter(engine=FakeLegacyTranslator())

    result = adapter.translate_batch(
        [TranslationInput(id="r1", text="hello")],
        TranslationOptions(source_language="English", target_language="Korean"),
    )

    assert result.translations == {"r1": "hello:Korean"}


def test_inpainting_adapter_converts_regions_to_boxes():
    adapter = InpaintingEngineAdapter(engine=FakeLegacyInpainter())
    image = ImageData(array=object(), explicit_width=100, explicit_height=100)

    result = adapter.inpaint(image, [InpaintRegion(box=Box(1, 2, 11, 12))], InpaintOptions())

    assert result.image is image


def test_rendering_adapter_returns_render_result():
    adapter = RenderingEngineAdapter(engine=FakeLegacyRenderer())
    image = ImageData(array=object(), explicit_width=100, explicit_height=100)

    result = adapter.render(image, [Bubble(id="b1", box=Box(1, 2, 11, 12), translated="안녕")], RenderOptions())

    assert result.image is image
