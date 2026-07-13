import numpy as np
import logging
import time
from threading import RLock
from typing import Any, List, Optional

from ...core.config import config_value
from .hybrid import HybridInpainter

logger = logging.getLogger(__name__)


class InpaintingService:
    def __init__(self, inpainter: Optional[HybridInpainter] = None, config: Any = None) -> None:
        self.inpainter: HybridInpainter = inpainter or HybridInpainter()
        self.config = config
        self._metrics_lock = RLock()
        self._prepared = False
        self._prepare_duration_ms: float | None = None
        self._last_inference_ms: float | None = None
        self._inference_count = 0

    def prepare(self, engine: str | None = None) -> None:
        resolved_engine = engine or config_value(self.config, "inpaint_engine")
        started = time.perf_counter()
        self.inpainter.prepare(resolved_engine)
        duration_ms = (time.perf_counter() - started) * 1000
        with self._metrics_lock:
            self._prepared = True
            self._prepare_duration_ms = duration_ms
        logger.info("Inpainting provider prepared: engine=%s duration_ms=%.0f", resolved_engine, duration_ms)

    def runtime_status(self) -> dict[str, Any]:
        with self._metrics_lock:
            return {
                "prepared": self._prepared,
                "prepare_duration_ms": self._prepare_duration_ms,
                "last_inference_ms": self._last_inference_ms,
                "inference_count": self._inference_count,
            }

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
            started = time.perf_counter()
            result = self.inpainter.inpaint(
                image,
                int_boxes,
                int_bubble_boxes,
                protect_edges=protect_edges,
                engine=resolved_engine,
                mask_dilation=resolved_dilation,
                clip_to_bubble=resolved_clip,
            )
            self._record_inference(started)
            return result
        started = time.perf_counter()
        result = self.inpainter.inpaint(
            image,
            int_boxes,
            protect_edges=protect_edges,
            engine=resolved_engine,
            mask_dilation=resolved_dilation,
            clip_to_bubble=resolved_clip,
        )
        self._record_inference(started)
        return result

    def _record_inference(self, started: float) -> None:
        duration_ms = (time.perf_counter() - started) * 1000
        with self._metrics_lock:
            self._last_inference_ms = duration_ms
            self._inference_count += 1

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
