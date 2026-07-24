import json
import threading

from backend.engines.translation.service import TranslationService


def test_translation_memory_save_is_recoverable_from_backup(tmp_path):
    service = object.__new__(TranslationService)
    service.tm_path = str(tmp_path / "translation_memory.json")
    service._cache = {"key": "first"}
    service._cache_lock = threading.RLock()
    service._save_tm()
    service._cache = {"key": "second"}
    service._save_tm()

    (tmp_path / "translation_memory.json").write_text("{broken", encoding="utf-8")
    recovered = object.__new__(TranslationService)
    recovered.tm_path = service.tm_path
    recovered._cache = {}
    recovered._cache_lock = threading.RLock()
    recovered._load_tm()

    assert recovered._cache == {"key": "first"}
    assert json.loads((tmp_path / "translation_memory.json.bak").read_text(encoding="utf-8")) == {"key": "first"}
