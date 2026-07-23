import unittest
import sys
import threading
import types
import base64
import hashlib
from dataclasses import replace
from unittest.mock import patch

import numpy as np
from backend.engines.translation import providers as translation_wrapper
from backend.core.config import AppConfig
from backend.engines.common.textblock import TextBlock
from backend.engines.translation.service import TranslationService
from backend.engines.translation.outcome import (
    VisionUnsupportedError,
)

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

    def test_vision_digest_and_payload_share_encoded_bytes(self):
        translator = (
            translation_wrapper.OpenAICompatibleTranslator(
                model="comic-model",
                supports_vision=True,
            )
        )
        image = np.zeros((24, 32, 3), dtype=np.uint8)
        digest, data_url = translator.prepare_vision_image(image)
        payload = translator._build_payload(
            [TextBlock(text="こんにちは")],
            "Japanese",
            "Korean",
            image=image,
            active_model="comic-model",
        )
        sent_url = payload["messages"][1]["content"][1][
            "image_url"
        ]["url"]
        encoded = base64.b64decode(
            sent_url.split(",", 1)[1]
        )

        self.assertEqual(sent_url, data_url)
        self.assertEqual(
            hashlib.sha256(encoded).hexdigest(),
            digest,
        )

    def test_translation_service_passes_common_retry_options_to_non_llm_provider(self):
        cfg = AppConfig(
            translation_provider="google",
            translation_max_retries=4,
            translation_retry_backoff_seconds=5,
        )

        translator = TranslationService(config=cfg).translator

        self.assertEqual(translator.max_retries, 4)
        self.assertEqual(translator.retry_backoff_seconds, 5)

    def test_cache_key_separates_compatible_endpoints(self):
        cfg = AppConfig(
            translation_provider="openai_compatible",
            translation_api_base_url="http://one.test/v1",
            translation_model="comic-model",
        )
        service = TranslationService(config=cfg)
        blocks = [TextBlock(text="台詞")]
        first = service._request_context(None)
        second = replace(
            first,
            endpoint_identity="http://two.test/v1/chat/completions",
        )
        self.assertNotEqual(
            service._cache_key(
                blocks, 0, "Japanese", "Korean", first
            ),
            service._cache_key(
                blocks, 0, "Japanese", "Korean", second
            ),
        )

    def test_vision_rejection_reuses_existing_text_only_cache(self):
        class FakeVisionTranslator:
            model = "configured-model"
            supports_vision = True
            temperature = 0.1
            top_p = 0.9
            max_tokens = 100
            api_url = "http://fake.test/v1"

            def __init__(self):
                self.calls = 0

            def effective_model(self):
                return "actual-model"

            def cache_endpoint_identity(self):
                return "http://fake.test/v1/chat/completions"

            def prepare_vision_image(self, _image):
                return "image-digest", "data:image/jpeg;base64,x"

            def translate_blocks(
                self, blocks, _source, _target, image
            ):
                self.calls += 1
                if image is not None:
                    self.supports_vision = False
                    raise VisionUnsupportedError("actual-model")
                for block in blocks:
                    block.translation = "network"
                return blocks

            def check_connection(self):
                return True

        cfg = AppConfig(
            translation_provider="openai_compatible",
            translation_cache_enabled=True,
        )
        translator = FakeVisionTranslator()
        service = TranslationService(cfg, translator=translator)
        block = TextBlock(text="台詞")
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        vision = service._request_context(image)
        text_only = replace(
            vision,
            vision_enabled=False,
            image_digest=None,
        )
        key = service._cache_key(
            [block], 0, "Japanese", "Korean", text_only
        )
        service._cache[key] = "cached text-only"

        service.translate_blocks(
            [block], "Japanese", "Korean", image
        )

        self.assertEqual(block.translation, "cached text-only")
        self.assertEqual(translator.calls, 1)

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

    def test_google_does_not_delete_mixed_script_ocr_text(self):
        received = []

        class FakeGoogleTranslator:
            def __init__(self, source, target):
                pass

            def translate(self, text):
                received.append(text)
                return text

        fake_module = types.SimpleNamespace(GoogleTranslator=FakeGoogleTranslator)
        block = TextBlock(text="日本語 주석은 유지")
        translator = translation_wrapper.GoogleTranslatorWrapper(max_retries=0, max_workers=1)

        with patch.dict(sys.modules, {"deep_translator": fake_module}):
            translator.translate_blocks([block], "Japanese", "Korean")

        self.assertEqual(received, ["日本語 주석은 유지"])

if __name__ == "__main__":
    unittest.main()
