from backend.infrastructure.runtime.providers import model_session_providers, session_providers


class FakeSession:
    def __init__(self, providers):
        self._providers = providers

    def get_providers(self):
        return self._providers


class FakeModel:
    def __init__(self):
        self.det = FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])
        self.rec = FakeSession(["CPUExecutionProvider"])
        self.other = object()


def test_session_provider_helper_reports_attached_providers():
    assert session_providers(FakeSession(["CUDAExecutionProvider"])) == ["CUDAExecutionProvider"]
    assert session_providers(object()) is None


def test_model_provider_helper_finds_nested_ocr_sessions():
    class Model:
        pass

    engine = Model()
    engine.model = Model()
    engine.model.encoder = FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])

    assert model_session_providers(engine) == ["CPUExecutionProvider", "CUDAExecutionProvider"]


def test_model_provider_helper_deduplicates_nested_sessions():
    assert model_session_providers(FakeModel()) == ["CPUExecutionProvider", "CUDAExecutionProvider"]
