import numpy as np
from typing import Any, List, Optional

from ...core.config import config_value
from .hybrid import HybridInpainter


class InpaintingService:
    def __init__(self, inpainter: Optional[HybridInpainter] = None, config: Any = None) -> None:
        self.inpainter: HybridInpainter = inpainter or HybridInpainter()
        self.config = config

    def clean_background(
        self,
        image: np.ndarray,
        boxes: List[List[float]],
        bubble_boxes: Optional[List[List[float]]] = None,
        protect_edges: bool = False,
        engine: str | None = None,
        mask_dilation: int | None = None,
        clip_to_bubble: bool | None = None,
    ) -> np.ndarray:
        """Removes text within the specified bounding boxes using inpainting."""
        resolved_engine = engine or config_value(self.config, "inpaint_engine")
        resolved_dilation = mask_dilation
        if resolved_dilation is None:
            resolved_dilation = config_value(self.config, "inpaint_mask_dilation")
        resolved_clip = clip_to_bubble
        if resolved_clip is None:
            resolved_clip = config_value(self.config, "inpaint_clip_to_bubble")

        int_boxes = [[int(val) for val in box] for box in boxes]
        if bubble_boxes is not None:
            int_bubble_boxes = [[int(val) for val in box] for box in bubble_boxes]
            return self.inpainter.inpaint(
                image,
                int_boxes,
                int_bubble_boxes,
                protect_edges=protect_edges,
                engine=resolved_engine,
                mask_dilation=resolved_dilation,
                clip_to_bubble=resolved_clip,
            )
        return self.inpainter.inpaint(
            image,
            int_boxes,
            protect_edges=protect_edges,
            engine=resolved_engine,
            mask_dilation=resolved_dilation,
            clip_to_bubble=resolved_clip,
        )

    def inpaint(
        self,
        image: np.ndarray,
        boxes: List[List[float]],
        bubble_boxes: Optional[List[List[float]]] = None,
        protect_edges: bool = False,
        engine: str | None = None,
        mask_dilation: int | None = None,
        clip_to_bubble: bool | None = None,
    ) -> np.ndarray:
        return self.clean_background(
            image,
            boxes,
            bubble_boxes=bubble_boxes,
            protect_edges=protect_edges,
            engine=engine,
            mask_dilation=mask_dilation,
            clip_to_bubble=clip_to_bubble,
        )