from types import SimpleNamespace

from backend.engines.inpainting.service import InpaintingService


class FakeInpainter:
    def __init__(self):
        self.prepared = []

    def prepare(self, engine):
        self.prepared.append(engine)


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
