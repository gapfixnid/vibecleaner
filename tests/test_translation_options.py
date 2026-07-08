import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from modules import translation_wrapper
from modules.config import AppConfig
from modules.utils.textblock import TextBlock
from services.translation_service import TranslationService


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


if __name__ == "__main__":
    unittest.main()
