import numpy as np
import logging
import time
import hashlib
import json
from collections import OrderedDict
from threading import RLock
from typing import Any, List, Optional

from ...core.config import config_value
from ...core.providers.concurrency import ProviderConcurrencyGate
from ...infrastructure.runtime.providers import model_session_providers
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
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._cache_limit = 4
        self._cache_hits = 0
        self._cache_misses = 0
        self._provider_gate = ProviderConcurrencyGate(max_concurrency=1, queue_capacity=2)

    def configure_queue(self, *, max_concurrency: int, queue_capacity: int) -> None:
        self._provider_gate = ProviderConcurrencyGate(
            max_concurrency=max_concurrency, queue_capacity=queue_capacity
        )

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
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_entries": len(self._cache),
                "queue": self._provider_gate.status(),
                "execution_providers": model_session_providers(
                    getattr(self.inpainter, "lama_model", None)
                ),
            }

    def clean_background(
        self,
        image: np.ndarray,
        boxes: List[List[float]],
        bubble_boxes: Optional[List[List[float]]] = None,
        source_polygons: Optional[List[List[List[tuple[int, int]]]]] = None,
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
        int_bubble_boxes = None
        if bubble_boxes is not None:
            int_bubble_boxes = [[int(val) for val in box] for box in bubble_boxes]
        int_source_polygons = None
        if source_polygons is not None:
            int_source_polygons = [
                [
                    [[int(point[0]), int(point[1])] for point in polygon]
                    for polygon in polygon_group
                ]
                for polygon_group in source_polygons
            ]
        cache_key = self._cache_key(
            image, int_boxes, int_bubble_boxes, int_source_polygons, protect_edges,
            resolved_engine, int(resolved_dilation), bool(resolved_clip),
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        if int_bubble_boxes is not None:
            started = time.perf_counter()
            with self._provider_gate.slot():
                result = self.inpainter.inpaint(
                    image,
                    int_boxes,
                    int_bubble_boxes,
                    source_polygons=int_source_polygons,
                    protect_edges=protect_edges,
                    engine=resolved_engine,
                    mask_dilation=resolved_dilation,
                    clip_to_bubble=resolved_clip,
                )
            self._record_inference(started)
            self._remember(cache_key, result)
            return result
        started = time.perf_counter()
        with self._provider_gate.slot():
            result = self.inpainter.inpaint(
                image,
                int_boxes,
                source_polygons=int_source_polygons,
                protect_edges=protect_edges,
                engine=resolved_engine,
                mask_dilation=resolved_dilation,
                clip_to_bubble=resolved_clip,
            )
        self._record_inference(started)
        self._remember(cache_key, result)
        return result

    def _cache_key(
        self,
        image: np.ndarray,
        boxes: list[list[int]],
        bubble_boxes: list[list[int]] | None,
        source_polygons: list[list[list[list[int]]]] | None,
        protect_edges: bool,
        engine: str,
        dilation: int,
        clip_to_bubble: bool,
    ) -> str:
        digest = hashlib.sha256()
        digest.update(str(image.shape).encode("ascii"))
        digest.update(str(image.dtype).encode("ascii"))
        digest.update(image.tobytes())
        digest.update(json.dumps(
            [boxes, bubble_boxes, source_polygons, protect_edges, engine, dilation, clip_to_bubble],
            separators=(",", ":"),
        ).encode("utf-8"))
        return digest.hexdigest()

    def _get_cached(self, key: str) -> np.ndarray | None:
        with self._metrics_lock:
            value = self._cache.get(key)
            if value is None:
                self._cache_misses += 1
                return None
            self._cache.move_to_end(key)
            self._cache_hits += 1
            return value.copy()

    def _remember(self, key: str, value: np.ndarray) -> None:
        with self._metrics_lock:
            self._cache[key] = value.copy()
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_limit:
                self._cache.popitem(last=False)

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
        source_polygons: Optional[List[List[List[tuple[int, int]]]]] = None,
        protect_edges: bool = False,
        engine: str | None = None,
        mask_dilation: int | None = None,
        clip_to_bubble: bool | None = None,
    ) -> np.ndarray:
        return self.clean_background(
            image,
            boxes,
            bubble_boxes=bubble_boxes,
            source_polygons=source_polygons,
            protect_edges=protect_edges,
            engine=engine,
            mask_dilation=mask_dilation,
            clip_to_bubble=clip_to_bubble,
        )
