# modules/translation_wrapper.py
import base64
import logging
import time

import cv2
import numpy as np
import requests

from modules.base_translator import BaseTranslator
from modules.constants import (
    OLLAMA_CONNECTION_TIMEOUT_SECONDS,
    OLLAMA_REQUEST_TIMEOUT_SECONDS,
)
from modules.utils.textblock import TextBlock
from modules.utils.translator_utils import (
    TranslationParseError,
    get_raw_text,
    set_texts_from_json,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleTranslator(BaseTranslator):
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8080/v1",
        model: str = "local-model",
        api_key: str = "",
        timeout_seconds: int = OLLAMA_REQUEST_TIMEOUT_SECONDS,
        supports_vision: bool = False,
    ):
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.supports_vision = supports_vision
        self.is_online = None
        self.installed_models: list[str] = []
        self.system_prompt_override = None
        self.last_error: str | None = None

    @property
    def completions_url(self) -> str:
        base = self.api_url.rstrip("/")
        return (
            f"{base}/chat/completions"
            if base.endswith("/v1")
            else f"{base}/v1/chat/completions"
        )

    @property
    def models_url(self) -> str:
        base = self.api_url.rstrip("/")
        return f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def check_connection(self) -> bool:
        try:
            response = requests.get(
                self.models_url,
                headers=self._headers(),
                timeout=OLLAMA_CONNECTION_TIMEOUT_SECONDS,
                proxies={"http": None, "https": None},
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", data.get("models", []))
                self.installed_models = [
                    str(model.get("id") or model.get("name"))
                    for model in models
                    if isinstance(model, dict)
                    and (model.get("id") or model.get("name"))
                ]
                self.is_online = True
                self.last_error = None
                return True
            self.last_error = f"HTTP {response.status_code}"
            logger.error(
                "Provider model list failed. url=%s status=%s",
                self.models_url,
                response.status_code,
            )
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception(
                "OpenAI-compatible connection check failed. api_url=%s", self.api_url
            )
        self.is_online = False
        self.installed_models = []
        return False

    def get_system_prompt(self, source_lang: str, target_lang: str) -> str:
        if getattr(self, "system_prompt_override", None):
            return self.system_prompt_override
        prompt = f"""You are a professional manga and comic localization translator.

Translate the text from {source_lang} to {target_lang} in the style of a professionally localized manga.

Requirements:
- Prioritize natural dialogue over literal translation.
- Preserve meaning, tone, emotion, character personality, and relationships.
- Rewrite expressions when necessary to sound natural in the target language.
- Avoid translationese, unnatural phrasing, and direct grammatical carryover from the source language.
- Use dialogue that sounds like native speakers in comics, webtoons, or animation.
- Keep lines concise and suitable for speech bubbles.
- Keep the translation close to the original length whenever possible.
- Maintain consistent names, terminology, and speaking style across all text blocks on the page.
- Adapt slang, jokes, idioms, honorifics, and cultural expressions naturally.
- Translate sound effects and reactions into natural comic expressions when appropriate.
- Use context and visual information to resolve obvious OCR errors and ambiguous text without inventing missing dialogue.

[Output format — MUST follow exactly]
- You will receive a JSON object whose values are the text blocks to translate (keys like "block_0", "block_1").
- Return ONLY the raw JSON object with the SAME keys, replacing each value with its translation.
- Do NOT translate, add, remove, or reorder keys.
- Do NOT wrap the output in markdown code fences. Output the pure JSON string only.
- Do NOT add explanations, notes, or commentary. Do NOT output <think> tags or any reasoning.
"""
        return prompt

    def translate_blocks(
        self,
        blocks: list[TextBlock],
        source_lang: str,
        target_lang: str,
        image: np.ndarray = None,
    ) -> list[TextBlock]:
        if not blocks:
            return blocks
        if self.is_online is None:
            self.check_connection()

        if not self.is_online:
            raise RuntimeError(
                self.last_error
                or "Translation provider is not reachable. Check the provider settings and your connection."
            )

        active_model = self._resolve_model()
        payload = self._build_payload(
            blocks, source_lang, target_lang, image, active_model
        )

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    self.completions_url,
                    json=payload,
                    headers=self._headers(),
                    timeout=self.timeout_seconds,
                    proxies={"http": None, "https": None},
                )
                if response.status_code != 200:
                    self.last_error = f"HTTP {response.status_code}"
                    body = response.text or ""
                    logger.error(
                        "Translation request failed. model=%s attempt=%s status=%s body=%s",
                        active_model,
                        attempt + 1,
                        response.status_code,
                        body[:500],
                    )
                    # Auto-recover: a text-only model rejecting the image -> drop
                    # the image and retry (and stop sending it this session).
                    lowered = body.lower()
                    if (
                        self.supports_vision
                        and image is not None
                        and ("image input is not supported" in lowered or "mmproj" in lowered)
                    ):
                        logger.warning(
                            "Model rejected image input; retrying without image (vision disabled for this session)."
                        )
                        self.supports_vision = False
                        payload = self._build_payload(blocks, source_lang, target_lang, image, active_model)
                    continue

                translated_text = self._extract_message_content(response)
                if set_texts_from_json(blocks, translated_text):
                    self.last_error = None
                    return blocks
                self.last_error = "Translation response did not match block keys"
                logger.error(
                    "Translation response did not apply to blocks. snippet=%s",
                    translated_text[:500],
                )
            except TranslationParseError as exc:
                self.last_error = str(exc)
                logger.exception(
                    "Translation response parsing failed. model=%s attempt=%s",
                    active_model,
                    attempt + 1,
                )
                break
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception(
                    "Translation request attempt failed. model=%s attempt=%s",
                    active_model,
                    attempt + 1,
                )

            if attempt < max_retries:
                time.sleep(2.0)

        raise RuntimeError(self.last_error or "Translation failed after multiple attempts.")

    def _resolve_model(self) -> str:
        active_model = self.model
        if self.installed_models and active_model not in self.installed_models:
            matching = [
                model
                for model in self.installed_models
                if active_model.split(":")[0] in model
            ]
            if not matching:
                matching = [
                    model
                    for model in self.installed_models
                    if "qwen" in model.lower() or "llama" in model.lower()
                ]
            active_model = matching[0] if matching else self.installed_models[0]
        return active_model

    def _build_payload(
        self,
        blocks: list[TextBlock],
        source_lang: str,
        target_lang: str,
        image: np.ndarray | None,
        active_model: str,
    ) -> dict:
        raw_text_json = get_raw_text(blocks)
        user_prompt = f"Make the translation sound as natural as possible.\nTranslate this:\n{raw_text_json}"
        user_content = [{"type": "text", "text": user_prompt}]

        if image is not None and self.supports_vision:
            image_url = self._image_to_data_url(image)
            if image_url:
                user_content.append(
                    {"type": "image_url", "image_url": {"url": image_url}}
                )

        return {
            "model": active_model,
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": self.get_system_prompt(source_lang, target_lang),
                        }
                    ],
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "top_p": 0.95,
        }

    def _image_to_data_url(self, image: np.ndarray) -> str | None:
        try:
            height, width = image.shape[:2]
            max_dim = 1024
            if max(height, width) > max_dim:
                scale = max_dim / max(height, width)
                image = cv2.resize(image, (int(width * scale), int(height * scale)))
            _, buffer = cv2.imencode(".jpg", image)
            img_base64 = base64.b64encode(buffer).decode("utf-8")
            return f"data:image/jpeg;base64,{img_base64}"
        except Exception:
            logger.exception(
                "Failed to encode image context for translation. model=%s", self.model
            )
            return None

    def _extract_message_content(self, response: requests.Response) -> str:
        data = response.json(strict=False)
        if not isinstance(data, dict):
            raise TranslationParseError("Translation response JSON is not an object")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise TranslationParseError("Translation response missing choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise TranslationParseError("Translation response missing message")
        content = str(message.get("content", "")).strip()
        if not content:
            raise TranslationParseError("Translation response content is empty")
        return content

    def _fallback_translate(self, text: str, target_lang: str) -> str:
        is_korean = target_lang in ["Korean", "한국어", "ko"]
        fallbacks = {
            "こんにちは！\nここは何処ですか？": (
                "안녕하세요!\n여기는 어디인가요?"
                if is_korean
                else "Hello!\nWhere is this place?"
            ),
            "ここは秘密の\nアトリエだよ。": (
                "여기는 비밀\n아틀리에야."
                if is_korean
                else "This is a secret\natelier."
            ),
            "ゴゴゴゴゴゴ… (SFX)": (
                "쿠구구구구궁... (효과음)"
                if is_korean
                else "Rumble rumble rumble... (SFX)"
            ),
            "OCRされた日本語テキスト입니다.": (
                "이것은 OCR 추출된 샘플 일본어 텍스트입니다."
                if is_korean
                else "This is the OCR'd Japanese text."
            ),
            "OCRされた日本語テキストです。": (
                "이것은 OCR 추출된 샘플 일본어 텍스트입니다."
                if is_korean
                else "This is the OCR'd Japanese text."
            ),
        }
        return fallbacks.get(text.strip(), "")


class OllamaTranslator(OpenAICompatibleTranslator):
    def __init__(self, api_url: str = "http://127.0.0.1:11434", model: str = "llama3", supports_vision: bool = True):
        super().__init__(
            api_url=api_url,
            model=model,
            api_key="ollama",
            timeout_seconds=OLLAMA_REQUEST_TIMEOUT_SECONDS,
            supports_vision=supports_vision,
        )

    @property
    def models_url(self) -> str:
        return f"{self.api_url}/api/tags"

    def check_connection(self) -> bool:
        try:
            response = requests.get(
                self.models_url,
                timeout=OLLAMA_CONNECTION_TIMEOUT_SECONDS,
                proxies={"http": None, "https": None},
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                self.installed_models = [model["name"] for model in models]
                self.is_online = True
                self.last_error = None
                return True
            self.last_error = f"HTTP {response.status_code}"
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("Ollama connection check failed. api_url=%s", self.api_url)
        self.is_online = False
        self.installed_models = []
        return False



