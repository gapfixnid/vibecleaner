import numpy as np

from backend.engines.detection.heuristic_lines.mask import _sum_box_pixels


def test_sum_box_pixels_clamps_exclusive_image_edge_coordinates():
    mask = np.zeros((3, 4), dtype=np.int32)
    mask[2, 3] = 1
    integral = mask.cumsum(axis=0).cumsum(axis=1)
    assert _sum_box_pixels(integral, 0, 0, 4, 3) == 1
