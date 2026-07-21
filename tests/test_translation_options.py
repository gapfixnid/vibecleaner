import unittest
import sys
import threading
import types
from unittest.mock import patch

from backend.engines.translation import providers as translation_wrapper
from backend.core.config import AppConfig
from backend.engines.common.textblock import TextBlock
from backend.engines.translation.service import TranslationService

class TranslationOptionsTests(unittest.TestCase):
    def test_openai_compatible_payload_uses_configurable_llm_options(self):
        translator = translation_wrapper.OpenAICompatibleTranslator(
            model="comic-model",
            temperature=0.2,
            top_p=0.8,
            max_tokens=1234,
        )

        payload = translator._build_payload(
            [TextBlock(text="こんにちは")],
            "Japanese",
            "Korean",
            image=None,
            active_model="comic-model",
        )

        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["top_p"], 0.8)
        self.assertEqual(payload["max_tokens"], 1234)

    def test_translation_service_passes_llm_options_from_config(self):
        cfg = AppConfig(
            translation_provider="openai_compatible",
            translation_api_base_url="http://localhost:1234/v1",
            translation_model="comic-model",
            translation_llm_temperature=0.15,
            translation_llm_top_p=0.85,
            translation_llm_max_tokens=2048,
            translation_max_retries=3,
            translation_retry_backoff_seconds=4,
        )

        translator = TranslationService(config=cfg).translator

        self.assertEqual(translator.temperature, 0.15)
        self.assertEqual(translator.top_p, 0.85)
        self.assertEqual(translator.max_tokens, 2048)
        self.assertEqual(translator.max_retries, 3)
        self.assertEqual(translator.retry_backoff_seconds, 4)

    def test_translation_service_passes_common_retry_options_to_non_llm_provider(self):
        cfg = AppConfig(
            translation_provider="google",
            translation_max_retries=4,
            translation_retry_backoff_seconds=5,
        )

        translator = TranslationService(config=cfg).translator

        self.assertEqual(translator.max_retries, 4)
        self.assertEqual(translator.retry_backoff_seconds, 5)

    def test_google_translates_blocks_concurrently_and_preserves_order(self):
        barrier = threading.Barrier(3)

        class FakeGoogleTranslator:
            def __init__(self, source, target):
                self.source = source
                self.target = target

            def translate(self, text):
                barrier.wait(timeout=2)
                return f"translated:{text}"

        fake_module = types.SimpleNamespace(GoogleTranslator=FakeGoogleTranslator)
        blocks = [TextBlock(text=f"台詞{i}") for i in range(3)]
        translator = translation_wrapper.GoogleTranslatorWrapper(
            max_retries=0,
            retry_backoff_seconds=0,
            max_workers=3,
        )

        with patch.dict(sys.modules, {"deep_translator": fake_module}):
            translator.translate_blocks(blocks, "Japanese", "Korean")

        self.assertEqual(
            [block.translation for block in blocks],
            ["translated:台詞0", "translated:台詞1", "translated:台詞2"],
        )

if __name__ == "__main__":
    unittest.main()
