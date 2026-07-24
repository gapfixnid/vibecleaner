import numpy as np

from backend.engines.detection.utils.slicer import ImageSlicer


def test_slicer_reuses_first_detection_and_honors_merged_slice_count():
    image = np.zeros((1000, 100, 3), dtype=np.uint8)
    slicer = ImageSlicer(
        height_to_width_ratio_threshold=1,
        target_slice_ratio=3,
        overlap_height_ratio=0.1,
        min_slice_height_ratio=0.7,
    )
    calls = []

    def detect(tile):
        calls.append(tile.shape[0])
        return np.empty((0, 4), dtype=np.float32), np.empty((0, 4), dtype=np.float32)

    _, _, effective, expected_count = slicer.calculate_slice_params(image)
    slicer.process_slices_for_detection(image, detect)

    assert len(calls) == expected_count
    assert expected_count == 3
    assert calls[-1] == image.shape[0] - (expected_count - 1) * effective


def test_slicer_probe_covers_full_height_when_merged_count_is_one():
    image = np.zeros((3600, 1000, 3), dtype=np.uint8)
    slicer = ImageSlicer(height_to_width_ratio_threshold=1, target_slice_ratio=3)
    calls = []

    def detect(tile):
        calls.append(tile.shape[0])
        return np.empty((0, 4), dtype=np.float32), np.empty((0, 4), dtype=np.float32)

    _, _, _, expected_count = slicer.calculate_slice_params(image)
    slicer.process_slices_for_detection(image, detect)
    assert expected_count == 1
    assert calls == [3600]
