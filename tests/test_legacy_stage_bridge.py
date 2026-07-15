from backend.core.models.geometry import Box
from backend.core.models.image import ImageData
from backend.core.models.text import TextRegion
from backend.core.ports.detection import DetectionOptions
from backend.core.ports.ocr import OcrOptions
from backend.pipeline.stages.legacy_bridge import LegacyDetectionAdapter, LegacyOcrAdapter


class LegacyBlock:
    def __init__(self, xyxy, text=""):
        self.xyxy = xyxy
        self.text = text


def test_legacy_detection_is_exposed_as_detection_result():
    adapter = LegacyDetectionAdapter(lambda image, **options: [LegacyBlock([1, 2, 8, 9])])
    result = adapter.detect(ImageData(array=object()), DetectionOptions())
    assert result.engine == "legacy"
    assert result.regions[0].box == Box(1, 2, 8, 9)


def test_legacy_ocr_updates_regions_and_returns_ocr_result():
    def recognize(image, blocks, *, engine):
        blocks[0].text = "translated source"

    region = TextRegion(Box(1, 2, 8, 9))
    result = LegacyOcrAdapter(recognize).recognize(
        ImageData(array=object()), [region], OcrOptions()
    )
    assert result.engine == "legacy"
    assert result.regions[0].text == "translated source"
