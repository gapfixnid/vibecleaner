from types import SimpleNamespace

import numpy as np

from backend.engines.inpainting.service import InpaintingService


class FakeInpainter:
    def __init__(self):
        self.prepared = []

    def prepare(self, engine):
        self.prepared.append(engine)

    def inpaint(self, image, boxes, bubble_boxes=None, **options):
        self.inpaint_calls = getattr(self, "inpaint_calls", 0) + 1
        result = image.copy()
        result[:] = 255
        return result


def test_inpainting_service_prepares_configured_engine():
    inpainter = FakeInpainter()
    service = InpaintingService(
        inpainter=inpainter,
        config=SimpleNamespace(inpaint_engine="lama"),
    )
    service.prepare()
    assert inpainter.prepared == ["lama"]
    status = service.runtime_status()
    assert status["prepared"] is True
    assert status["prepare_duration_ms"] is not None
    assert status["inference_count"] == 0


def test_inpainting_service_can_prepare_explicit_engine():
    inpainter = FakeInpainter()
    service = InpaintingService(
        inpainter=inpainter,
        config=SimpleNamespace(inpaint_engine="lama"),
    )
    service.prepare("opencv")
    assert inpainter.prepared == ["opencv"]


def test_inpainting_service_reuses_bounded_result_cache():
    inpainter = FakeInpainter()
    service = InpaintingService(
        inpainter=inpainter,
        config=SimpleNamespace(
            inpaint_engine="lama", inpaint_mask_dilation=2,
            inpaint_clip_to_bubble=True,
        ),
    )
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    first = service.clean_background(image, [[1, 1, 4, 4]])
    second = service.clean_background(image, [[1, 1, 4, 4]])
    assert inpainter.inpaint_calls == 1
    assert np.array_equal(first, second)
    assert first is not second
    status = service.runtime_status()
    assert status["cache_hits"] == 1
    assert status["cache_misses"] == 1
