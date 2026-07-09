# engines/detection/wrapper.py
import logging

import cv2
import numpy as np
from .factory import DetectionEngineFactory
from ..common.textblock import TextBlock

logger = logging.getLogger(__name__)


class DetectorUnavailableError(RuntimeError):
    """Raised when the detection engine is unavailable or fails at runtime."""


class DummySettings:
    def is_gpu_enabled(self):
        import onnxruntime as ort
        try:
            providers = ort.get_available_providers()
            return "CUDAExecutionProvider" in providers or "ROCMExecutionProvider" in providers
        except Exception:
            return False

class RTDETRv2Detector:
    def __init__(self):
        self.settings = DummySettings()
        self.engine_error: str | None = None
        try:
            self.engine = DetectionEngineFactory.create_engine(self.settings, backend='onnx')
        except Exception as exc:
            self.engine_error = str(exc)
            logger.exception("Failed to initialize RT-DETR-v2 detection engine")
            self.engine = None
        
    def detect_bubbles(
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
        """
        Detect text bubble and free text areas.
        Returns a list of TextBlock objects.
        """
        if self.engine is None:
            detail = f": {self.engine_error}" if self.engine_error else ""
            raise DetectorUnavailableError(f"Detection engine is unavailable{detail}")
            
        try:
            # Convert BGR to RGB for detection
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            blocks = self.engine.detect(
                rgb_image,
                model_name=model_name,
                confidence_threshold=confidence_threshold,
                tiling_enabled=tiling_enabled,
                bubbles_only=bubbles_only,
                line_merge_sensitivity=line_merge_sensitivity,
                smart_direction=smart_direction,
                text_direction_override=text_direction_override,
            )
            return blocks
        except Exception as exc:
            logger.exception("RT-DETR detection failed")
            raise DetectorUnavailableError(f"Detection failed: {exc}") from exc

    @property
    def available(self) -> bool:
        return self.engine is not None