import os
import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

from infrastructure.runtime.device import get_providers
from infrastructure.downloads import ModelDownloader, ModelID, models_base_dir
from infrastructure.runtime.onnx import make_session
from engines.common.textblock import TextBlock
from engines.detection.utils.slicer import ImageSlicer
from .base import DetectionEngine


class YoloONNXDetection(DetectionEngine):
    """Generic YOLOv8/v11 ONNX text and speech bubble detector.
    """

    def __init__(self, settings=None):
        super().__init__(settings)
        self.session = None
        self.device = 'cpu'
        self.confidence_threshold = 0.45
        self.iou_threshold = 0.5
        self.model_dir = os.path.join(models_base_dir, 'detection')

        self.image_slicer = ImageSlicer(
            height_to_width_ratio_threshold=3.5,
            target_slice_ratio=3.0,
            overlap_height_ratio=0.2,
            min_slice_height_ratio=0.7
        )

    def initialize(
        self,
        device: str = 'cpu',
        confidence_threshold: float = 0.45,
        model_name: str | None = None,
        tiling_enabled: bool | None = None,
    ) -> None:
        self.device = device
        self.confidence_threshold = confidence_threshold
        model_name = model_name or "ysgyolo.onnx"
        self.current_loaded_model = model_name
        self.tiling_enabled = True if tiling_enabled is None else bool(tiling_enabled)
        
        # Resolve file path
        # Check if the exact filename exists in models/detection
        file_path = os.path.join(self.model_dir, model_name)
        if not os.path.exists(file_path):
            # Check if any .onnx file with 'ysg' or 'yolo' is in models_base_dir/detection/
            if os.path.exists(self.model_dir):
                for f in os.listdir(self.model_dir):
                    if f.endswith('.onnx') and ('ysg' in f.lower() or 'yolo' in f.lower()):
                        file_path = os.path.join(self.model_dir, f)
                        break
        
        if not os.path.exists(file_path):
            # Fallback to default RT-DETR model
            model_id = ModelID.RTDETR_V2_ONNX
            ModelDownloader.ensure([model_id])
            file_path = ModelDownloader.get_file_path(model_id, 'detector.onnx')
            
        providers = get_providers(self.device)
        self.session = make_session(file_path, sess_options=None, providers=providers)

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
        model_name = model_name or getattr(self, "current_loaded_model", "ysgyolo.onnx")
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
        h_orig, w_orig = image.shape[:2]
        
        # Resize BGR image to 640x640 for YOLO
        im_resized = cv2.resize(image, (640, 640))
        # Convert to float32 [0, 1] RGB
        arr = np.asarray(im_resized, dtype=np.float32) / 255.0
        arr = np.transpose(arr, (2, 0, 1))  # (3, 640, 640)
        im_data = arr[np.newaxis, ...]  # (1, 3, 640, 640)

        # Run model
        outputs = self.session.run(None, {self.session.get_inputs()[0].name: im_data})
        output0 = outputs[0]  # shape: (1, 4+num_classes, 8400)
        
        if output0.ndim == 3 and output0.shape[0] == 1:
            output0 = output0[0]  # (4+num_classes, 8400)
            
        # Parse boxes (center_x, center_y, width, height, class0_score, class1_score, ...)
        predictions = output0.T  # (8400, 4+num_classes)
        
        boxes = []
        scores = []
        class_ids = []
        
        for pred in predictions:
            coords = pred[:4]
            cls_scores = pred[4:]
            class_id = np.argmax(cls_scores)
            score = cls_scores[class_id]
            
            if score > self.confidence_threshold:
                cx, cy, w_box, h_box = coords
                x1 = (cx - w_box / 2.0) * (w_orig / 640.0)
                y1 = (cy - h_box / 2.0) * (h_orig / 640.0)
                x2 = (cx + w_box / 2.0) * (w_orig / 640.0)
                y2 = (cy + h_box / 2.0) * (h_orig / 640.0)
                
                boxes.append([x1, y1, x2, y2])
                scores.append(float(score))
                class_ids.append(int(class_id))
                
        if not boxes:
            return np.array([]), np.array([])
            
        # Apply Non-Maximum Suppression (NMS)
        indices = cv2.dnn.NMSBoxes(
            bboxes=[[int(b[0]), int(b[1]), int(b[2]-b[0]), int(b[3]-b[1])] for b in boxes],
            scores=scores,
            score_threshold=self.confidence_threshold,
            nms_threshold=self.iou_threshold
        )
        
        bubble_boxes = []
        text_boxes = []
        
        if len(indices) > 0:
            for idx in indices.flatten():
                box = boxes[idx]
                class_id = class_ids[idx]
                x1, y1, x2, y2 = map(int, box)
                
                # Class 0 -> speech bubble, Class 1+ -> text
                if class_id == 0:
                    bubble_boxes.append([x1, y1, x2, y2])
                else:
                    text_boxes.append([x1, y1, x2, y2])
                    
        bubble_boxes = np.array(bubble_boxes) if bubble_boxes else np.array([])
        text_boxes = np.array(text_boxes) if text_boxes else np.array([])
        return bubble_boxes, text_boxes
