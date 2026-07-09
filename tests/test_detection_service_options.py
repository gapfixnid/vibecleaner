from types import SimpleNamespace

import numpy as np

from backend.engines.detection.service import DetectionService

class FakeBlock:
    def __init__(self):
        self.xyxy = [1, 2, 11, 12]
        self.text = ""

class FakeDetector:
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
        return [FakeBlock()]

class FakeOcr:
    def __init__(self):
        self.lang = None

    def recognize_text(self, image, blocks, engine=None):
        for block in blocks:
            block.text = f"{engine}:text"
        return blocks

def test_detection_service_passes_explicit_detection_options_from_config():
    detector = FakeDetector()
    service = DetectionService(
        detector=detector,
        ocr_engine=FakeOcr(),
        config=SimpleNamespace(
            detect_model="Small (INT8)",
            confidence_threshold=0.61,
            tiling_enabled=False,
            bubbles_only=True,
            line_merge_sensitivity=1.9,
            smart_direction=False,
            text_direction_override="vertical",
            ocr_engine="ppocr",
        ),
    )

    blocks = service.detect_and_ocr(np.zeros((16, 16, 3), dtype=np.uint8), lang="Japanese")

    assert detector.calls[0]["model_name"] == "Small (INT8)"
    assert detector.calls[0]["confidence_threshold"] == 0.61
    assert detector.calls[0]["tiling_enabled"] is False
    assert detector.calls[0]["bubbles_only"] is True
    assert detector.calls[0]["line_merge_sensitivity"] == 1.9
    assert detector.calls[0]["smart_direction"] is False
    assert detector.calls[0]["text_direction_override"] == "vertical"
    assert blocks[0].text == "ppocr:text"
