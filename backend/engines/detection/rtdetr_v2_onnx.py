import os
import numpy as np
import onnxruntime as ort
from PIL import Image

from infrastructure.runtime.device import get_providers
from infrastructure.downloads import ModelDownloader, ModelID, models_base_dir
from infrastructure.runtime.onnx import make_session
from engines.common.textblock import TextBlock
from engines.detection.utils.slicer import ImageSlicer
from .base import DetectionEngine


def _make_rtdetr_session_options():
    so = ort.SessionOptions()
    so.log_severity_level = 3
    # Small CPU RT-DETR runs benefit from explicit sequential execution
    # and a modest intra-op thread count instead of ORT defaults.
    so.intra_op_num_threads = 4
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    so.enable_cpu_mem_arena = True
    so.enable_mem_pattern = True
    return so


class RTDetrV2ONNXDetection(DetectionEngine):
    """RT-DETR-v2 ONNX backend detection engine.
    """

    def __init__(self, settings=None):
        super().__init__(settings)
        self.session = None
        self.device = 'cpu'
        self.confidence_threshold = 0.3
        self.model_dir = os.path.join(models_base_dir, 'detection')

        self.image_slicer = ImageSlicer(
            height_to_width_ratio_threshold=3.5,
            target_slice_ratio=3.0,
            overlap_height_ratio=0.1,
            min_slice_height_ratio=0.7
        )

    def initialize(
        self, 
        device: str = 'cpu', 
        confidence_threshold: float = 0.3,
        model_name: str | None = None,
        tiling_enabled: bool | None = None,
    ) -> None:
        self.device = device
        self.confidence_threshold = confidence_threshold
        model_name = model_name or "High Precision (FP32)"
        self.current_loaded_model = model_name
        self.tiling_enabled = True if tiling_enabled is None else bool(tiling_enabled)

        if model_name in {"Small (INT8)", "Small (INT8) [기본값]"}:
            model_id = ModelID.RTDETR_INT8_ONNX
            filename = 'detector-v4-s_int8.onnx'
        else:
            model_id = ModelID.RTDETR_V2_ONNX
            filename = 'detector.onnx'

        ModelDownloader.ensure([model_id])
        file_path = ModelDownloader.get_file_path(model_id, filename)
        providers = get_providers(self.device)
        self.session = make_session(file_path, sess_options=_make_rtdetr_session_options(), providers=providers)

    def detect(
        self,
        image: np.ndarray,
        model_name: str | None = None,
        confidence_threshold: float | None = None,
        tiling_enabled: bool | None = None,
        bubbles_only: bool | None = None,
        line_merge_sensitivity: float | None = None,
        smart_direction: bool | None = None,
        text_direction_override: str | None = None,
    ) -> list[TextBlock]:
        model_name = model_name or getattr(self, "current_loaded_model", "High Precision (FP32)")
        if getattr(self, "current_loaded_model", None) != model_name:
            self.initialize(
                device=self.device,
                confidence_threshold=self.confidence_threshold,
                model_name=model_name,
                tiling_enabled=tiling_enabled,
            )

        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold

        tiling_enabled = getattr(self, "tiling_enabled", True) if tiling_enabled is None else bool(tiling_enabled)
        if not tiling_enabled:
            bubble_boxes, text_boxes = self._detect_single_image(image)
        else:
            bubble_boxes, text_boxes = self.image_slicer.process_slices_for_detection(
                image, self._detect_single_image
            )
        return self.create_text_blocks(
            image,
            text_boxes,
            bubble_boxes,
            bubbles_only=bubbles_only,
            line_merge_sensitivity=line_merge_sensitivity,
            smart_direction=smart_direction,
            text_direction_override=text_direction_override,
        )

    def _detect_single_image(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        pil_image = Image.fromarray(image)  # image is already in RGB format

        # preprocess to (1,3,H,W) float32
        im_resized = pil_image.resize((640, 640))
        arr = np.asarray(im_resized, dtype=np.float32) / 255.0  # (H,W,3)
        arr = np.transpose(arr, (2, 0, 1))  # (3,H,W)
        im_data = arr[np.newaxis, ...]  # (1,3,H,W)

        w, h = pil_image.size
        orig_size = np.array([[w, h]], dtype=np.int64)

        outputs = self.session.run(None, {
            "images": im_data,
            "orig_target_sizes": orig_size
        })

        # expected outputs: labels, boxes, scores
        labels, boxes, scores = outputs[:3]

        if isinstance(labels, np.ndarray) and labels.ndim == 2 and labels.shape[0] == 1:
            labels = labels[0]
        if isinstance(scores, np.ndarray) and scores.ndim == 2 and scores.shape[0] == 1:
            scores = scores[0]
        if isinstance(boxes, np.ndarray) and boxes.ndim == 3 and boxes.shape[0] == 1:
            boxes = boxes[0]

        bubble_boxes = []
        text_boxes = []
        for lab, box, scr in zip(labels, boxes, scores):
            if float(scr) < float(self.confidence_threshold):
                continue
            x1, y1, x2, y2 = map(int, box)
            label_id = int(lab)
            if label_id == 0:
                bubble_boxes.append([x1, y1, x2, y2])
            elif label_id in [1, 2]:
                text_boxes.append([x1, y1, x2, y2])

        bubble_boxes = np.array(bubble_boxes) if bubble_boxes else np.array([])
        text_boxes = np.array(text_boxes) if text_boxes else np.array([])
        return bubble_boxes, text_boxes
