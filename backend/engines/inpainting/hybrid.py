# engines/inpainting/hybrid.py
import numpy as np
import cv2
from threading import RLock

class HybridInpainter:
    def __init__(self):
        class DummySettings:
            def is_gpu_enabled(self):
                import onnxruntime as ort
                try:
                    providers = ort.get_available_providers()
                    return "CUDAExecutionProvider" in providers or "ROCMExecutionProvider" in providers
                except Exception:
                    return False
        self.settings = DummySettings()
        self.lama_model = None
        self._model_lock = RLock()

    def _resolve_engine_name(self, engine: str | None = None) -> str:
        requested = str(engine or "lama").strip().lower()
        if requested in {"opencv", "fast", "speed", "telea"}:
            return "opencv"
        return "lama"

    def _get_deep_model(self, engine_name: str):
        device = "cuda" if self.settings.is_gpu_enabled() else "cpu"
        with self._model_lock:
            if self.lama_model is None:
                import logging
                logging.info("Initializing LaMa inpainting model...")
                from .lama import LaMa
                self.lama_model = LaMa(device=device, backend="onnx")
        return self.lama_model

    def prepare(self, engine: str = "lama") -> None:
        engine_name = self._resolve_engine_name(engine)
        if engine_name != "opencv":
            self._get_deep_model(engine_name)

    def inpaint(
        self,
        image: np.ndarray,
        boxes: list[list[int]],
        bubble_boxes: list[list[int]] | None = None,
        protect_edges: bool = False,
        engine: str = "lama",
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
                
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue
                
            # Convert crop to grayscale to isolate text strokes
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            
            # Find the dominant background color of the crop using the median of all pixels.
            crop_median_color = np.median(crop, axis=(0, 1))
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
            
            # 3. Connected Components filtering to prune dusts and screen-tones
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(refined_mask)
            min_area = max(1, min(3, int(gray.size * 0.0001)))
            final_mask = np.zeros_like(refined_mask)
            for i in range(1, num_labels):
                if stats[i, cv2.CC_STAT_AREA] >= min_area:
                    final_mask[labels == i] = 255
            
            if np.any(final_mask):
                # 3b. Edge protection (for single-bubble inpaint to preserve bubble borders)
                if protect_edges:
                    edge_margin = max(5, min(crop.shape[:2]) // 15)
                    edge_filter = np.zeros_like(final_mask)
                    edge_filter[edge_margin:-edge_margin, edge_margin:-edge_margin] = 255
                    final_mask = cv2.bitwise_and(final_mask, edge_filter)
                    if not np.any(final_mask):
                        continue

                # 4. Adaptive dilation based on estimated stroke width using Distance Transform
                dist_transform = cv2.distanceTransform(final_mask, cv2.DIST_L2, 3)
                max_dist = np.percentile(dist_transform[dist_transform > 0], 90) if np.any(dist_transform > 0) else 1.0
                configured_dilation = max(1, int(mask_dilation))
                radius = max(configured_dilation + 1, int(round(max_dist * 1.8)))
                kernel_size = 2 * radius + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                mask = cv2.dilate(final_mask, kernel, iterations=1)
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
                        inpainted_crop = cv2.inpaint(crop, mask, 3, cv2.INPAINT_TELEA)

                inpainted[y1:y2, x1:x2] = inpainted_crop
            else:
                pass
                
        return inpainted

