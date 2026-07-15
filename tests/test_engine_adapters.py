from backend.core.models.geometry import Box
from backend.core.models.image import ImageData
from backend.core.models.page import Bubble
from backend.core.models.text import TextRegion
from backend.core.ports.detection import DetectionOptions
from backend.core.ports.inpainting import InpaintOptions, InpaintRegion
from backend.core.ports.ocr import OcrOptions
from backend.core.ports.rendering import RenderOptions
from backend.core.ports.translation import TranslationInput, TranslationOptions
from backend.engines.detection.adapter import DetectionEngineAdapter
from backend.engines.inpainting.adapter import InpaintingEngineAdapter
from backend.engines.ocr.adapter import OcrEngineAdapter
from backend.engines.rendering.adapter import RenderingEngineAdapter
from backend.engines.translation.adapter import TranslationEngineAdapter


class FakeLegacyBlock:
    def __init__(self, xyxy, text=""):
        self.xyxy = xyxy
        self.text = text
        self.translation = ""


class FakeLegacyDetector:
    def __init__(self):
        self.initialize_calls = []
        self.detect_calls = []

    def initialize(self, **kwargs):
        self.initialize_calls.append(kwargs)

    def detect(self, image):
        self.detect_calls.append({"image": image})
        return [FakeLegacyBlock([1, 2, 11, 12])]


class FakeDetectBubblesDetector:
    def __init__(self):
        self.calls = []

    def detect_bubbles(
        self,
        image,
        model_name=None,
        confidence_threshold=None,
        tiling_enabled=None,
        bubbles_only=None,
        line_merge_sensitivity=None,
        smart_direction=None,
        text_direction_override=None,
    ):
        self.calls.append(
            {
                "image": image,
                "model_name": model_name,
                "confidence_threshold": confidence_threshold,
                "tiling_enabled": tiling_enabled,
                "bubbles_only": bubbles_only,
                "line_merge_sensitivity": line_merge_sensitivity,
                "smart_direction": smart_direction,
                "text_direction_override": text_direction_override,
            }
        )
        return [FakeLegacyBlock([3, 4, 13, 14])]


class FakeLegacyOcr:
    def __init__(self):
        self.calls = []

    def recognize(self, image, regions, options):
        self.calls.append({"image": image, "regions": regions, "options": options})
        return ["こんにちは"]


class FakeRecognizeTextOcr:
    def __init__(self):
        self.calls = []

    def recognize_text(
        self,
        image,
        blocks,
        engine=None,
        padding=None,
        crop_scale=None,
        adaptive_binarization=None,
        adaptive_binarization_strength=None,
    ):
        self.calls.append(
            {
                "image": image,
                "blocks": blocks,
                "engine": engine,
                "padding": padding,
                "crop_scale": crop_scale,
                "adaptive_binarization": adaptive_binarization,
                "adaptive_binarization_strength": adaptive_binarization_strength,
            }
        )
        for block in blocks:
            block.text = f"{engine}:{block.xyxy[0]}"
        return blocks


class ReorderingRecognizeTextOcr(FakeRecognizeTextOcr):
    def recognize_text(self, image, blocks, **kwargs):
        return [
            type("Result", (), {"xyxy": blocks[1].xyxy, "text": "second"})(),
            type("Result", (), {"xyxy": blocks[0].xyxy, "text": "first"})(),
        ]


class FakeLegacyTranslator:
    def translate(self, text, source_language, target_language):
        return f"{text}:{target_language}"


class FakeLegacyInpainter:
    def __init__(self):
        self.calls = []

    def inpaint(
        self,
        image,
        boxes,
        bubble_boxes=None,
        protect_edges=False,
        engine=None,
        mask_dilation=None,
        clip_to_bubble=None,
    ):
        self.calls.append(
            {
                "boxes": boxes,
                "bubble_boxes": bubble_boxes,
                "protect_edges": protect_edges,
                "engine": engine,
                "mask_dilation": mask_dilation,
                "clip_to_bubble": clip_to_bubble,
            }
        )
        return image


class FakeLegacyRenderer:
    def render(self, image, bubbles, options):
        return image


def test_detection_adapter_converts_legacy_blocks_to_regions():
    detector = FakeLegacyDetector()
    adapter = DetectionEngineAdapter(engine=detector)
    image = ImageData(array=None, explicit_width=100, explicit_height=100, mode="RGB")

    result = adapter.detect(image, DetectionOptions())

    assert result.regions[0].box == Box(x1=1, y1=2, x2=11, y2=12)


def test_detection_adapter_passes_explicit_options_to_legacy_engine():
    detector = FakeLegacyDetector()
    adapter = DetectionEngineAdapter(engine=detector)
    options = DetectionOptions(
        model_name="Small (INT8)",
        confidence_threshold=0.67,
        tiling_enabled=False,
    )

    adapter.detect(ImageData(array=object()), options)

    assert detector.initialize_calls[0]["model_name"] == "Small (INT8)"
    assert detector.initialize_calls[0]["confidence_threshold"] == 0.67
    assert detector.initialize_calls[0]["tiling_enabled"] is False


def test_detection_adapter_wraps_detect_bubbles_legacy_engine():
    detector = FakeDetectBubblesDetector()
    adapter = DetectionEngineAdapter(engine=detector)

    result = adapter.detect(
        ImageData(array=object()),
        DetectionOptions(
            model_name="Small (INT8)",
            confidence_threshold=0.52,
            tiling_enabled=False,
        ),
    )

    assert detector.calls[0]["model_name"] == "Small (INT8)"
    assert detector.calls[0]["confidence_threshold"] == 0.52
    assert detector.calls[0]["tiling_enabled"] is False
    assert result.regions[0].box == Box(x1=3, y1=4, x2=13, y2=14)


def test_detection_adapter_passes_explicit_postprocess_options():
    detector = FakeDetectBubblesDetector()
    adapter = DetectionEngineAdapter(engine=detector)

    adapter.detect(
        ImageData(array=object()),
        DetectionOptions(
            bubbles_only=True,
            line_merge_sensitivity=1.8,
            smart_direction=False,
            text_direction_override="horizontal",
        ),
    )

    assert detector.calls[0]["bubbles_only"] is True
    assert detector.calls[0]["line_merge_sensitivity"] == 1.8
    assert detector.calls[0]["smart_direction"] is False
    assert detector.calls[0]["text_direction_override"] == "horizontal"


def test_ocr_adapter_adds_recognized_text_to_regions():
    ocr = FakeLegacyOcr()
    adapter = OcrEngineAdapter(engine=ocr)
    region = TextRegion(box=Box(1, 2, 11, 12))

    result = adapter.recognize(ImageData(array=None), [region], OcrOptions())

    assert result.regions[0].text == "こんにちは"


def test_ocr_adapter_passes_explicit_options_to_legacy_engine():
    ocr = FakeLegacyOcr()
    adapter = OcrEngineAdapter(engine=ocr)
    options = OcrOptions(engine="ppocr", padding=12, crop_scale=2.0)

    adapter.recognize(ImageData(array=None), [TextRegion(box=Box(1, 2, 11, 12))], options)

    assert ocr.calls[0]["options"] is options


def test_ocr_adapter_wraps_recognize_text_legacy_engine():
    ocr = FakeRecognizeTextOcr()
    adapter = OcrEngineAdapter(engine=ocr)
    region = TextRegion(box=Box(1, 2, 11, 12))

    result = adapter.recognize(
        ImageData(array=object()),
        [region],
        OcrOptions(engine="ppocr"),
    )

    assert ocr.calls[0]["engine"] == "ppocr"
    assert ocr.calls[0]["blocks"][0].xyxy == [1, 2, 11, 12]
    assert result.regions[0].text == "ppocr:1"


def test_ocr_adapter_matches_reordered_results_by_coordinates():
    adapter = OcrEngineAdapter(engine=ReorderingRecognizeTextOcr())
    regions = [
        TextRegion(box=Box(1, 2, 11, 12)),
        TextRegion(box=Box(20, 22, 31, 32)),
    ]

    result = adapter.recognize(ImageData(array=object()), regions, OcrOptions())

    assert [region.text for region in result.regions] == ["first", "second"]


def test_ocr_adapter_passes_explicit_crop_options_to_legacy_engine():
    ocr = FakeRecognizeTextOcr()
    adapter = OcrEngineAdapter(engine=ocr)

    adapter.recognize(
        ImageData(array=object()),
        [TextRegion(box=Box(1, 2, 11, 12))],
        OcrOptions(
            engine="ppocr",
            padding=14,
            crop_scale=2.5,
            adaptive_binarization=False,
            adaptive_binarization_strength=3.5,
        ),
    )

    assert ocr.calls[0]["padding"] == 14
    assert ocr.calls[0]["crop_scale"] == 2.5
    assert ocr.calls[0]["adaptive_binarization"] is False
    assert ocr.calls[0]["adaptive_binarization_strength"] == 3.5


def test_translation_adapter_returns_translation_map():
    adapter = TranslationEngineAdapter(engine=FakeLegacyTranslator())

    result = adapter.translate_batch(
        [TranslationInput(id="r1", text="hello")],
        TranslationOptions(source_language="English", target_language="Korean"),
    )

    assert result.translations == {"r1": "hello:Korean"}


def test_inpainting_adapter_converts_regions_to_boxes():
    inpainter = FakeLegacyInpainter()
    adapter = InpaintingEngineAdapter(engine=inpainter)
    image = ImageData(array=object(), explicit_width=100, explicit_height=100)

    result = adapter.inpaint(image, [InpaintRegion(box=Box(1, 2, 11, 12))], InpaintOptions())

    assert result.image is image


def test_inpainting_adapter_passes_explicit_options_to_legacy_engine():
    inpainter = FakeLegacyInpainter()
    adapter = InpaintingEngineAdapter(engine=inpainter)
    image = ImageData(array=object(), explicit_width=100, explicit_height=100)

    adapter.inpaint(
        image,
        [InpaintRegion(box=Box(1, 2, 11, 12), bubble_box=Box(0, 1, 12, 13))],
        InpaintOptions(engine="opencv", mask_dilation=5, clip_to_bubble=False),
    )

    assert inpainter.calls[0]["engine"] == "opencv"
    assert inpainter.calls[0]["mask_dilation"] == 5
    assert inpainter.calls[0]["clip_to_bubble"] is False
    assert inpainter.calls[0]["bubble_boxes"] == [[0, 1, 12, 13]]


def test_rendering_adapter_returns_render_result():
    adapter = RenderingEngineAdapter(engine=FakeLegacyRenderer())
    image = ImageData(array=object(), explicit_width=100, explicit_height=100)

    result = adapter.render(image, [Bubble(id="b1", box=Box(1, 2, 11, 12), translated="안녕")], RenderOptions())

    assert result.image is image
