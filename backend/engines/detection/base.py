from abc import ABC, abstractmethod
import numpy as np
from typing import Optional

from ..common.textblock import TextBlock
from .backend import resolve_detection_backend
from .pipeline import DetectionPipeline


class DetectionEngine(ABC):
    """
    Abstract base class for all detection engines.
    Each model implementation should inherit from this class.
    """
    
    def __init__(self, settings=None):
        self.settings = settings
        self.backend = resolve_detection_backend()
        self.pipeline = DetectionPipeline(settings=self.settings, backend=self.backend)
    
    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """
        Initialize the detection model with necessary parameters.
        
        Args:
            **kwargs: Engine-specific initialization parameters
        """
        pass
    
    @abstractmethod
    def detect(self, image: np.ndarray) -> list[TextBlock]:
        """
        Detect text blocks in an image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of TextBlock objects with detected regions
        """
        pass
        
    def create_text_blocks(
        self, 
        image: np.ndarray,
        text_boxes: np.ndarray,
        bubble_boxes: Optional[np.ndarray] = None,
        bubbles_only: bool | None = None,
        line_merge_sensitivity: float | None = None,
        smart_direction: bool | None = None,
        text_direction_override: str | None = None,
        text_confidences: dict[tuple[int, int, int, int], float] | None = None,
    ) -> list[TextBlock]:
        return self.pipeline.build_text_blocks(
            image,
            text_boxes,
            bubble_boxes,
            bubbles_only=bubbles_only,
            line_merge_sensitivity=line_merge_sensitivity,
            smart_direction=smart_direction,
            text_direction_override=text_direction_override,
            text_confidences=text_confidences,
        )
