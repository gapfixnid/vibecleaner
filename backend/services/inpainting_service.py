import numpy as np
from typing import List, Optional
from modules.inpainting_wrapper import HybridInpainter


class InpaintingService:
    def __init__(self, inpainter: Optional[HybridInpainter] = None) -> None:
        self.inpainter: HybridInpainter = inpainter or HybridInpainter()

    def clean_background(
        self,
        image: np.ndarray,
        boxes: List[List[float]],
        bubble_boxes: Optional[List[List[float]]] = None,
        protect_edges: bool = False,
    ) -> np.ndarray:
        """Removes text within the specified bounding boxes using inpainting."""
        int_boxes = [[int(val) for val in box] for box in boxes]
        if bubble_boxes is not None:
            int_bubble_boxes = [[int(val) for val in box] for box in bubble_boxes]
            return self.inpainter.inpaint(image, int_boxes, int_bubble_boxes, protect_edges=protect_edges)
        return self.inpainter.inpaint(image, int_boxes, protect_edges=protect_edges)
