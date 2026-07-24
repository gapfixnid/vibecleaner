import pytest

from backend.engines.translation.providers import (
    FatalProviderHttpError,
    OpenAICompatibleTranslator,
)
from backend.engines.common.textblock import TextBlock


class Response:
    def __init__(self, status, body=""):
        self.status_code = status
        self.text = body
        self.headers = {}


def test_fatal_http_status_is_not_retried(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.engines.translation.providers.requests.post", lambda *a, **k: (calls.append(1) or Response(401)))
    translator = OpenAICompatibleTranslator(max_retries=3, retry_backoff_seconds=0)
    translator.is_online = True
    with pytest.raises(FatalProviderHttpError):
        translator.translate_blocks([TextBlock(text="x")], "Japanese", "Korean")
    assert len(calls) == 1


def test_retryable_http_status_uses_retry_budget(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.engines.translation.providers.requests.post", lambda *a, **k: (calls.append(1) or Response(500)))
    translator = OpenAICompatibleTranslator(max_retries=2, retry_backoff_seconds=0)
    translator.is_online = True
    with pytest.raises(RuntimeError):
        translator.translate_blocks([TextBlock(text="x")], "Japanese", "Korean")
    assert len(calls) == 3
