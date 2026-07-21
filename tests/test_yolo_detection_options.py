from unittest.mock import patch

import numpy as np

import backend.engines.detection.yolo_onnx as yolo_module
from backend.engines.detection.yolo_onnx import YoloONNXDetection

class FakeSession:
    def get_inputs(self):
        return [type("Input", (), {"name": "images"})()]

    def run(self, *_args, **_kwargs):
        return [np.zeros((1, 6, 0), dtype=np.float32)]


class FakeSegmentationSession(FakeSession):
    def run(self, *_args, **_kwargs):
        predictions = np.zeros((1, 37, 100), dtype=np.float32)
        predictions[0, :5, 0] = [320, 320, 160, 120, 0.9]
        prototypes = np.zeros((1, 32, 160, 160), dtype=np.float32)
        return [predictions, prototypes]

def test_yolo_initialize_uses_explicit_model_name_without_global_config():
    created_paths = []

    def fake_exists(path):
        return str(path).endswith("custom-yolo.onnx")

    def fake_make_session(path, sess_options=None, providers=None):
        created_paths.append(path)
        return FakeSession()

    detector = YoloONNXDetection()

    with (
        patch.object(yolo_module.os.path, "exists", side_effect=fake_exists),
        patch.object(yolo_module, "get_providers", return_value=["CPUExecutionProvider"]),
        patch.object(yolo_module, "make_session", side_effect=fake_make_session),
    ):
        detector.initialize(
            device="cpu",
            model_name="custom-yolo.onnx",
            confidence_threshold=0.66,
            tiling_enabled=False,
        )

    assert created_paths[0].endswith("custom-yolo.onnx")
    assert detector.current_loaded_model == "custom-yolo.onnx"
    assert detector.confidence_threshold == 0.66
    assert detector.tiling_enabled is False

def test_yolo_detect_uses_explicit_confidence_and_tiling_options():
    detector = YoloONNXDetection()
    detector.session = FakeSession()
    detector.current_loaded_model = "custom-yolo.onnx"
    calls = []

    def fake_detect_single(image):
        calls.append(
            {
                "shape": image.shape,
                "confidence_threshold": detector.confidence_threshold,
            }
        )
        return np.array([]), np.array([])

    detector._detect_single_image = fake_detect_single

    detector.detect(
        np.zeros((12, 10, 3), dtype=np.uint8),
        model_name="custom-yolo.onnx",
        confidence_threshold=0.72,
        tiling_enabled=False,
    )

    assert len(calls) == 1
    assert calls[0]["confidence_threshold"] == 0.72


def test_yolo_segmentation_export_uses_only_the_bubble_class_score():
    detector = YoloONNXDetection()
    detector.session = FakeSegmentationSession()
    detector.confidence_threshold = 0.45

    bubbles, text = detector._detect_single_image(np.zeros((640, 640, 3), dtype=np.uint8))

    assert bubbles.shape == (1, 4)
    assert text.size == 0
