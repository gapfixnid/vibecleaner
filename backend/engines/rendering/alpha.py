from __future__ import annotations

import numpy as np


def compose_final_alpha(
    fill_alpha: np.ndarray,
    stroke_only_alpha: np.ndarray,
) -> np.ndarray:
    """Compose stroke behind fill with the canonical integer SourceOver rule."""
    if fill_alpha.shape != stroke_only_alpha.shape:
        raise ValueError("TEXT_LAYER_ALPHA_SHAPE_MISMATCH")
    fill_u16 = np.asarray(fill_alpha, dtype=np.uint16)
    stroke_u16 = np.asarray(stroke_only_alpha, dtype=np.uint16)
    return (
        fill_u16
        + stroke_u16 * (255 - fill_u16) // 255
    ).astype(np.uint8)
