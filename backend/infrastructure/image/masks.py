"""Bubble-aware mask construction helpers."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .morphology import close_holes, erode, get_structuring_element, MORPH_CROSS
from .transforms import connected_components


@dataclass(frozen=True)
class BubbleClipMaskResult:
    mask: np.ndarray
    source: str
    boundary_contact_ratio: float | None = None


def build_bubble_clip_mask(
    mask_shape: tuple[int, int],
    bounds: tuple[int, int, int, int],
    bubble_xyxy,
    *,
    inset: int,
    image: np.ndarray | None = None,
    seed_bbox: tuple[int, int, int, int] | None = None,
    return_metadata: bool = False,
) -> np.ndarray | BubbleClipMaskResult | None:
    if bubble_xyxy is None or len(bubble_xyxy) < 4:
        return None

    x1, y1, x2, y2 = [int(v) for v in bounds]
    bx1, by1, bx2, by2 = [int(v) for v in bubble_xyxy[:4]]

    # Calculate relative coordinates for fallback ellipse
    bx1_rel = bx1 + inset - x1
    by1_rel = by1 + inset - y1
    bx2_rel = bx2 - inset - x1
    by2_rel = by2 - inset - y1

    height, width = mask_shape[:2]

    use_fallback = True

    if image is not None:
        try:
            # Let's perform bubble segmentation!
            H, W = image.shape[:2]

            # Crop bubble region with a safety margin to avoid boundary effects
            margin = 5
            crop_y1 = max(0, by1 - margin)
            crop_y2 = min(H, by2 + margin)
            crop_x1 = max(0, bx1 - margin)
            crop_x2 = min(W, bx2 + margin)

            bubble_crop = image[crop_y1:crop_y2, crop_x1:crop_x2]

            # Convert to grayscale
            if bubble_crop.ndim == 3:
                gray = (0.299 * bubble_crop[..., 2] + 0.587 * bubble_crop[..., 1] + 0.114 * bubble_crop[..., 0]).astype(np.uint8)
            else:
                gray = bubble_crop.copy()

            # Define seed region relative to crop
            if seed_bbox is not None:
                sx1, sy1, sx2, sy2 = [int(v) for v in seed_bbox[:4]]
            else:
                # Fallback seed to center of bubble
                sx1 = (bx1 + bx2) // 2 - 5
                sx2 = (bx1 + bx2) // 2 + 5
                sy1 = (by1 + by2) // 2 - 5
                sy2 = (by1 + by2) // 2 + 5

            seed_y1_rel = max(0, sy1 - crop_y1)
            seed_y2_rel = min(crop_y2 - crop_y1, sy2 - crop_y1)
            seed_x1_rel = max(0, sx1 - crop_x1)
            seed_x2_rel = min(crop_x2 - crop_x1, sx2 - crop_x1)

            seed_region = gray[seed_y1_rel:seed_y2_rel, seed_x1_rel:seed_x2_rel]

            if seed_region.size > 0:
                # Find the dominant background color inside the seed area
                hist, bin_edges = np.histogram(seed_region, bins=16, range=(0, 256))
                max_bin = np.argmax(hist)
                bg_val = (bin_edges[max_bin] + bin_edges[max_bin + 1]) / 2.0

                tolerance = 20
                bg_mask = np.abs(gray - bg_val) <= tolerance

                num_labels, labeled = connected_components(bg_mask, connectivity=4)

                # Find all labels that appear in the seed_bbox
                seed_pixels_mask = bg_mask[seed_y1_rel:seed_y2_rel, seed_x1_rel:seed_x2_rel]
                seed_labels = labeled[seed_y1_rel:seed_y2_rel, seed_x1_rel:seed_x2_rel][seed_pixels_mask]
                unique_labels = np.unique(seed_labels)
                unique_labels = unique_labels[unique_labels > 0]

                if unique_labels.size > 0:
                    bubble_mask = np.isin(labeled, unique_labels)

                    # The bubble box inside the crop is at:
                    b_y1_rel = by1 - crop_y1
                    b_y2_rel = by2 - crop_y1
                    b_x1_rel = bx1 - crop_x1
                    b_x2_rel = bx2 - crop_x1

                    # Extract border pixels of the segmented bubble mask to check touch ratio
                    border_mask_pixels = []
                    if 0 <= b_y1_rel < bubble_mask.shape[0]:
                        border_mask_pixels.extend(bubble_mask[b_y1_rel, max(0, b_x1_rel):min(bubble_mask.shape[1], b_x2_rel)])
                    if 0 <= b_y2_rel - 1 < bubble_mask.shape[0]:
                        border_mask_pixels.extend(bubble_mask[b_y2_rel - 1, max(0, b_x1_rel):min(bubble_mask.shape[1], b_x2_rel)])
                    if 0 <= b_x1_rel < bubble_mask.shape[1]:
                        border_mask_pixels.extend(bubble_mask[max(0, b_y1_rel):min(bubble_mask.shape[0], b_y2_rel), b_x1_rel])
                    if 0 <= b_x2_rel - 1 < bubble_mask.shape[1]:
                        border_mask_pixels.extend(bubble_mask[max(0, b_y1_rel):min(bubble_mask.shape[0], b_y2_rel), b_x2_rel - 1])

                    border_mask_pixels = np.array(border_mask_pixels)
                    if border_mask_pixels.size > 0:
                        touch_ratio = np.mean(border_mask_pixels)
                    else:
                        touch_ratio = 0.0

                    # If the segmented mask touches more than 50% of the bubble border,
                    # it means it leaked to the outside (no outline/boundary contained it).
                    if touch_ratio < 0.5:
                        use_fallback = False

                    if not use_fallback:
                        # Fill holes to include text and ink inside the bubble
                        bubble_mask = close_holes(bubble_mask)

                        # Apply inset by eroding the mask. For the segmented path, we cap the
                        # inset to 2 pixels to keep the mask close to the outline without touching it.
                        seg_inset = min(2, inset)
                        if seg_inset > 0:
                            struct_elem = get_structuring_element(MORPH_CROSS, (3, 3))
                            bubble_mask = erode(bubble_mask.astype(np.uint8) * 255, struct_elem, iterations=seg_inset) > 0

                        # Now map back to the coordinate space of bounds
                        final_clip = np.zeros(mask_shape, dtype=bool)

                        # Calculate overlap between bounds and crop
                        overlap_y1 = max(y1, crop_y1)
                        overlap_y2 = min(y2, crop_y2)
                        overlap_x1 = max(x1, crop_x1)
                        overlap_x2 = min(x2, crop_x2)

                        if overlap_y2 > overlap_y1 and overlap_x2 > overlap_x1:
                            # slice in final_clip
                            f_y1 = overlap_y1 - y1
                            f_y2 = overlap_y2 - y1
                            f_x1 = overlap_x1 - x1
                            f_x2 = overlap_x2 - x1

                            # slice in bubble_mask
                            b_y1 = overlap_y1 - crop_y1
                            b_y2 = overlap_y2 - crop_y1
                            b_x1 = overlap_x1 - crop_x1
                            b_x2 = overlap_x2 - crop_x1

                            final_clip[f_y1:f_y2, f_x1:f_x2] = bubble_mask[b_y1:b_y2, b_x1:b_x2]

                        if return_metadata:
                            return BubbleClipMaskResult(
                                final_clip,
                                "detector_component",
                                float(touch_ratio),
                            )
                        return final_clip
        except Exception:
            # Fall back to ellipse on any error
            pass

    cy_grid, cx_grid = np.ogrid[:height, :width]
    ellipse_cx = (bx1_rel + bx2_rel) / 2.0
    ellipse_cy = (by1_rel + by2_rel) / 2.0
    rx = max(1.0, (bx2_rel - bx1_rel) / 2.0)
    ry = max(1.0, (by2_rel - by1_rel) / 2.0)
    ellipse = (
        ((cx_grid - ellipse_cx) / rx) ** 2
        + ((cy_grid - ellipse_cy) / ry) ** 2
        <= 1.0
    )
    if return_metadata:
        return BubbleClipMaskResult(
            ellipse,
            "ellipse",
            None,
        )
    return ellipse
