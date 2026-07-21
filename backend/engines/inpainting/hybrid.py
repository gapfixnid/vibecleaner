# engines/inpainting/hybrid.py
import numpy as np
import cv2
import math
from threading import RLock
from ...infrastructure.model_catalog import resolve_model


def build_oriented_target_mask(
    polygons: list[list[list[int]]] | None,
    *,
    origin_x: int,
    origin_y: int,
    width: int,
    height: int,
    margin: int,
) -> np.ndarray | None:
    """Build a locally expanded mask that follows rotated text-line geometry."""
    if not polygons:
        return None
    target = np.zeros((height, width), dtype=np.uint8)
    for polygon in polygons:
        points = np.asarray(polygon, dtype=np.float32)
        if points.ndim != 2 or points.shape[0] < 4 or points.shape[1] != 2:
            continue
        points[:, 0] -= origin_x
        points[:, 1] -= origin_y
        center, size, angle = cv2.minAreaRect(points)
        expanded_size = (
            max(1.0, float(size[0]) + margin * 2),
            max(1.0, float(size[1]) + margin * 2),
        )
        expanded = cv2.boxPoints((center, expanded_size, angle))
        cv2.fillConvexPoly(target, np.rint(expanded).astype(np.int32), 255)
    return target if np.any(target) else None


def _polygon_is_slanted(polygon) -> bool:
    points = np.asarray(polygon, dtype=np.float32)
    if points.ndim != 2 or points.shape[0] < 4 or points.shape[1] != 2:
        return False
    edge = points[1] - points[0]
    angle = abs(math.degrees(math.atan2(float(edge[1]), float(edge[0])))) % 90.0
    return min(angle, 90.0 - angle) >= 3.0

class HybridInpainter:
    def __init__(self):
        class DummySettings:
            def is_gpu_enabled(self):
                import onnxruntime as ort
                try:
                    providers = ort.get_available_providers()
                    return "CUDAExecutionProvider" in providers
                except Exception:
                    return False
        self.settings = DummySettings()
        self.lama_model = None
        self._models = {}
        self._model_lock = RLock()

    def _resolve_engine_name(self, engine: str | None = None) -> str:
        requested = str(engine or "aot").strip().lower()
        if requested in {"opencv", "fast", "speed", "telea"}:
            return "opencv"
        return str(engine or "aot")

    def _get_deep_model(self, engine_name: str):
        device = "cuda" if self.settings.is_gpu_enabled() else "cpu"
        with self._model_lock:
            if engine_name not in self._models:
                import logging
                option = resolve_model("inpainting", engine_name)
                logging.info("Initializing %s inpainting model...", option.family)
                if option.family == "aot":
                    from .aot import AOT
                    model_class = AOT
                else:
                    from .lama import LaMa
                    model_class = LaMa
                model_path = option.paths[0] if option.paths else None
                self._models[engine_name] = model_class(
                    device=device, backend="onnx", model_path=model_path
                )
                self.lama_model = self._models[engine_name]
        return self._models[engine_name]

    def prepare(self, engine: str = "aot") -> None:
        engine_name = self._resolve_engine_name(engine)
        if engine_name != "opencv":
            self._get_deep_model(engine_name)

    def inpaint(
        self,
        image: np.ndarray,
        boxes: list[list[int]],
        bubble_boxes: list[list[int]] | None = None,
        source_polygons: list[list[list[list[int]]]] | None = None,
        protect_edges: bool = False,
        engine: str = "aot",
        mask_dilation: int = 2,
        clip_to_bubble: bool = True,
    ) -> np.ndarray:
        """
        Clears text areas using the selected inpainting engine on text stroke masks.
        """
        inpainted = image.copy()
        h, w = image.shape[:2]
        engine_name = self._resolve_engine_name(engine)
        
        for index, box in enumerate(boxes):
            x1, y1, x2, y2 = [int(v) for v in box]
            # Add padding to prevent mask clipping and boundary residue cutoff at crop edges
            padding = 8
            x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
            x2, y2 = min(w, x2 + padding), min(h, y2 + padding)
            if x2 <= x1 or y2 <= y1:
                continue
                
            crop = inpainted[y1:y2, x1:x2].copy()
            if crop.size == 0:
                continue
                
            # Convert crop to grayscale to isolate text strokes
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            polygon_group = (
                source_polygons[index]
                if source_polygons is not None and index < len(source_polygons)
                else None
            )
            # Slanted glyphs expose antialiased tips outside a tight polygon.
            # Expand only those regions; a global increase would reach ordinary
            # speech-bubble borders and recreate the earlier smearing issue.
            has_slanted_text = bool(polygon_group) and any(
                _polygon_is_slanted(polygon) for polygon in polygon_group
            )
            effective_dilation = max(int(mask_dilation), 8) if has_slanted_text else int(mask_dilation)
            target_mask = build_oriented_target_mask(
                polygon_group,
                origin_x=x1,
                origin_y=y1,
                width=crop.shape[1],
                height=crop.shape[0],
                margin=max(4, effective_dilation * 2),
            )
            
            # Estimate the background from the oriented text regions. A whole
            # speech-bubble crop may contain panel art or a dark outline whose
            # median is unrelated to the paper behind diagonal lettering.
            target_pixels = crop[target_mask > 0] if target_mask is not None else crop.reshape(-1, 3)
            crop_median_color = np.median(target_pixels, axis=0)
            bg_gray = int(0.299 * crop_median_color[2] + 0.587 * crop_median_color[1] + 0.114 * crop_median_color[0])
            
            # 1. Adaptive Thresholding for local lighting variation
            block_size = min(31, max(3, int(min(gray.shape[:2]) / 4) | 1))
            if bg_gray > 127:
                # Light background: Extract dark strokes
                binary = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, block_size, C=3
                )
            else:
                # Dark background: Extract light strokes
                binary = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, block_size, C=-3
                )
                
            # 2. Contrast Cutoff to filter out minor gradients and screen-tone noises
            contrast_mask = np.zeros_like(gray)
            if bg_gray > 127:
                contrast_mask[gray < max(30, bg_gray - 12)] = 255
            else:
                contrast_mask[gray > min(225, bg_gray + 12)] = 255
            
            refined_mask = cv2.bitwise_and(binary, contrast_mask)
            if target_mask is not None:
                refined_mask = cv2.bitwise_and(refined_mask, target_mask)
            
            # 3. Connected Components filtering to prune dusts and screen-tones
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(refined_mask)
            min_area = max(1, min(3, int(gray.size * 0.0001)))
            final_mask = np.zeros_like(refined_mask)
            for i in range(1, num_labels):
                if stats[i, cv2.CC_STAT_AREA] >= min_area:
                    final_mask[labels == i] = 255
            
            if np.any(final_mask):
                # 3b. Edge protection (for single-bubble inpaint to preserve bubble borders)
                if protect_edges and target_mask is None:
                    edge_margin = max(5, min(crop.shape[:2]) // 15)
                    edge_filter = np.zeros_like(final_mask)
                    edge_filter[edge_margin:-edge_margin, edge_margin:-edge_margin] = 255
                    final_mask = cv2.bitwise_and(final_mask, edge_filter)
                    if not np.any(final_mask):
                        continue

                # 4. Adaptive dilation based on estimated stroke width using Distance Transform
                dist_transform = cv2.distanceTransform(final_mask, cv2.DIST_L2, 3)
                max_dist = np.percentile(dist_transform[dist_transform > 0], 90) if np.any(dist_transform > 0) else 1.0
                configured_dilation = max(1, effective_dilation)
                radius = max(configured_dilation + 1, int(round(max_dist * 1.8)))
                kernel_size = 2 * radius + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                mask = cv2.dilate(final_mask, kernel, iterations=1)
                if target_mask is not None:
                    mask = cv2.bitwise_and(mask, target_mask)
                if clip_to_bubble and bubble_boxes and index < len(bubble_boxes):
                    bx1, by1, bx2, by2 = [int(v) for v in bubble_boxes[index]]
                    bx1, by1 = max(0, bx1), max(0, by1)
                    bx2, by2 = min(w, bx2), min(h, by2)
                    clip = np.zeros_like(mask)
                    local_x1 = max(0, bx1 - x1)
                    local_y1 = max(0, by1 - y1)
                    local_x2 = min(mask.shape[1], bx2 - x1)
                    local_y2 = min(mask.shape[0], by2 - y1)
                    if local_x2 > local_x1 and local_y2 > local_y1:
                        clip[local_y1:local_y2, local_x1:local_x2] = 255
                        mask = cv2.bitwise_and(mask, clip)
                
                if engine_name == "opencv":
                    inpainted_crop = cv2.inpaint(crop, mask, 3, cv2.INPAINT_TELEA)
                else:
                    try:
                        from .schema import Config as InpaintConfig
                        # Convert BGR crop to RGB for the deep inpainting models.
                        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                        model = self._get_deep_model(engine_name)
                        inpainted_rgb = model(crop_rgb, mask, config=InpaintConfig())
                        if inpainted_rgb.dtype != np.uint8:
                            inpainted_rgb = np.clip(inpainted_rgb, 0, 255).astype(np.uint8)

                        inpainted_crop = cv2.cvtColor(inpainted_rgb, cv2.COLOR_RGB2BGR)
                    except Exception:
                        import logging
                        logging.exception("%s inpainting failed; falling back to Telea CV2 inpainting", engine_name)
                        if str(engine_name).startswith("custom:"):
                            raise
                        inpainted_crop = cv2.inpaint(crop, mask, 3, cv2.INPAINT_TELEA)

                # Some model backends can slightly alter known pixels. Always
                # composite explicitly so speech-bubble borders and artwork
                # outside the final mask remain byte-for-byte unchanged.
                composited_crop = np.where(mask[:, :, None] > 0, inpainted_crop, crop)
                inpainted[y1:y2, x1:x2] = composited_crop
            else:
                pass
                
        return inpainted

