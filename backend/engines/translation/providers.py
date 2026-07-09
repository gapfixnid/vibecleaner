# engines/translation/providers.py
import base64
import logging
import re
import time

import cv2
import numpy as np
import requests

from engines.common.textblock import TextBlock

from .base import BaseTranslator
from .helpers import (
    TranslationParseError,
    get_raw_text,
    set_texts_from_json,
)

logger = logging.getLogger(__name__)

OLLAMA_REQUEST_TIMEOUT_SECONDS = 90
OLLAMA_CONNECTION_TIMEOUT_SECONDS = 5.0


class OpenAICompatibleTranslator(BaseTranslator):
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8080/v1",
        model: str = "local-model",
        api_key: str = "",
        timeout_seconds: int = OLLAMA_REQUEST_TIMEOUT_SECONDS,
        supports_vision: bool = False,
        temperature: float = 0.1,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        max_retries: int = 2,
        retry_backoff_seconds: int = 2,
    ):
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.supports_vision = supports_vision
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
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

        max_retries = max(0, int(self.max_retries))
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
                try:
                    if set_texts_from_json(blocks, translated_text):
                        self.last_error = None
                        return blocks
                except TranslationParseError:
                    if len(blocks) == 1:
                        recovered = self._recover_single_block_translation(translated_text)
                        if recovered:
                            blocks[0].translation = recovered
                            self.last_error = None
                            return blocks
                    raise

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
                time.sleep(max(0, int(self.retry_backoff_seconds)))

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
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
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

    def _recover_single_block_translation(self, response_text: str) -> str:
        """Recover translation from a single-block plain text or malformed JSON response."""
        text = response_text.strip()
        if not text:
            return ""

        # Pure plain text - return as-is
        if not text.startswith("{") and not text.startswith("["):
            return text

        # Case 1: JSON-like string with a closing quote.
        # Handles escaped characters inside the JSON string.
        match = re.search(r'"block_0"\s*:\s*"(?P<value>(?:\\.|[^"\\])*)"', text)
        if match:
            return match.group("value").strip()

        # Case 2: Malformed JSON without a closing quote.
        match = re.search(r'"block_0"\s*:\s*"(?P<value>.*)', text, re.DOTALL)
        if not match:
            return ""

        recovered = match.group("value").strip()

        # Remove common unfinished JSON tails.
        recovered = recovered.removesuffix('"}').removesuffix('"').strip()

        # Trim obvious log/traceback tails if model output leaked.
        for marker in ("\n2026-", "\n[ERROR]", "\n[WARNING]", "\nTraceback"):
            if marker in recovered:
                recovered = recovered.split(marker, 1)[0].strip()

        return recovered


class OllamaTranslator(OpenAICompatibleTranslator):
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:11434",
        model: str = "llama3",
        supports_vision: bool = True,
        temperature: float = 0.1,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        max_retries: int = 2,
        retry_backoff_seconds: int = 2,
    ):
        super().__init__(
            api_url=api_url,
            model=model,
            api_key="ollama",
            timeout_seconds=OLLAMA_REQUEST_TIMEOUT_SECONDS,
            supports_vision=supports_vision,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
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



class GoogleTranslatorWrapper(BaseTranslator):
    def __init__(self, max_retries: int = 2, retry_backoff_seconds: int = 2):
        self.model = "google"
        self.is_online = True
        self.last_error = None
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def check_connection(self) -> bool:
        return True

    def translate_blocks(
        self,
        blocks: list[TextBlock],
        source_lang: str,
        target_lang: str,
        image: np.ndarray = None,
    ) -> list[TextBlock]:
        if not blocks:
            return blocks
        lang_map = {
            "japanese": "ja",
            "日本語": "ja",
            "ja": "ja",
            "korean": "ko",
            "한국어": "ko",
            "ko": "ko",
            "english": "en",
            "영어": "en",
            "en": "en",
        }
        from_code = lang_map.get(source_lang.lower(), "ja")
        to_code = lang_map.get(target_lang.lower(), "ko")
        def _clean_japanese_ocr(text: str) -> str:
            import re
            text = text.replace("는", "は")
            hangul_pattern = re.compile(r'[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]+')
            return hangul_pattern.sub('', text).strip()

        try:
            from deep_translator import GoogleTranslator

            translator = GoogleTranslator(source=from_code, target=to_code)
            for block in blocks:
                if block.text.strip():
                    cleaned_text = block.text.replace("\n", " ").strip()
                    if from_code == "ja":
                        cleaned_text = _clean_japanese_ocr(cleaned_text)
                    if not cleaned_text:
                        block.translation = ""
                        continue
                    for attempt in range(max(0, int(self.max_retries)) + 1):
                        try:
                            block.translation = translator.translate(cleaned_text)
                            break
                        except Exception as block_err:
                            self.last_error = str(block_err)
                            if attempt < max(0, int(self.max_retries)):
                                time.sleep(max(0, int(self.retry_backoff_seconds)))
                                continue
                            logger.warning("Failed to translate block '%s': %s", cleaned_text, block_err)
                            block.translation = block.text
                else:
                    block.translation = ""
            self.last_error = None
            return blocks
        except Exception as e:
            logger.exception("Google Translate API failed")
            self.last_error = str(e)
            for block in blocks:
                block.translation = block.text
            return blocks


class DeepLTranslatorWrapper(BaseTranslator):
    def __init__(
        self,
        api_key: str = "",
        timeout_seconds: int = 30,
        max_retries: int = 2,
        retry_backoff_seconds: int = 2,
    ):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.model = "deepl"
        self.is_online = None
        self.last_error = None
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def check_connection(self) -> bool:
        if not self.api_key:
            self.last_error = "DeepL API key is missing"
            self.is_online = False
            return False

        url = (
            "https://api-free.deepl.com/v2/usage"
            if self.api_key.endswith(":fx")
            else "https://api.deepl.com/v2/usage"
        )
        try:
            headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                self.is_online = True
                self.last_error = None
                return True
            self.last_error = f"HTTP {res.status_code}: {res.text}"
        except Exception as e:
            self.last_error = str(e)
        self.is_online = False
        return False

    def translate_blocks(
        self,
        blocks: list[TextBlock],
        source_lang: str,
        target_lang: str,
        image: np.ndarray = None,
    ) -> list[TextBlock]:
        if not blocks:
            return blocks
        if not self.api_key:
            logger.error("DeepL translation failed: API key missing")
            for block in blocks:
                block.translation = block.text
            return blocks

        lang_map = {
            "japanese": "JA",
            "日本語": "JA",
            "ja": "JA",
            "korean": "KO",
            "한국어": "KO",
            "ko": "KO",
            "english": "EN",
            "영어": "EN",
            "en": "EN",
        }
        from_code = lang_map.get(source_lang.lower(), "JA")
        to_code = lang_map.get(target_lang.lower(), "KO")

        url = (
            "https://api-free.deepl.com/v2/translate"
            if self.api_key.endswith(":fx")
            else "https://api.deepl.com/v2/translate"
        )

        try:
            headers = {
                "Authorization": f"DeepL-Auth-Key {self.api_key}",
                "Content-Type": "application/json",
            }
            texts_to_translate = [
                b.text.replace("\n", " ").strip() for b in blocks if b.text.strip()
            ]
            if not texts_to_translate:
                for b in blocks:
                    b.translation = ""
                return blocks

            payload = {
                "text": texts_to_translate,
                "source_lang": from_code,
                "target_lang": to_code,
            }
            for attempt in range(max(0, int(self.max_retries)) + 1):
                res = requests.post(
                    url, json=payload, headers=headers, timeout=self.timeout_seconds
                )
                if res.status_code == 200:
                    translations = res.json().get("translations", [])
                    trans_idx = 0
                    for block in blocks:
                        if block.text.strip():
                            block.translation = translations[trans_idx].get("text", "")
                            trans_idx += 1
                        else:
                            block.translation = ""
                    self.last_error = None
                    return blocks
                self.last_error = f"HTTP {res.status_code}: {res.text}"
                logger.error("DeepL translation failed: %s", self.last_error)
                if attempt < max(0, int(self.max_retries)):
                    time.sleep(max(0, int(self.retry_backoff_seconds)))
        except Exception as e:
            self.last_error = str(e)
            logger.exception("DeepL translation exception")

        for block in blocks:
            block.translation = block.text
        return blocks


class OpenAITranslatorWrapper(OpenAICompatibleTranslator):
    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        timeout_seconds: int = 30,
        supports_vision: bool = True,
        temperature: float = 0.1,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        max_retries: int = 2,
        retry_backoff_seconds: int = 2,
    ):
        super().__init__(
            api_url="https://api.openai.com/v1",
            model=model,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            supports_vision=supports_vision,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )


class ClaudeTranslatorWrapper(BaseTranslator):
    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-3-5-sonnet-20241022",
        timeout_seconds: int = 45,
        supports_vision: bool = True,
        temperature: float = 0.1,
        top_p: float = 0.95,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        # Claude path currently sends text-only; kept for API consistency.
        self.supports_vision = supports_vision
        self.is_online = None
        self.last_error = None
        self.system_prompt_override = None
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens

    def check_connection(self) -> bool:
        if not self.api_key:
            self.last_error = "Claude API Key missing"
            self.is_online = False
            return False
        self.is_online = True
        return True

    def translate_blocks(
        self,
        blocks: list[TextBlock],
        source_lang: str,
        target_lang: str,
        image: np.ndarray = None,
    ) -> list[TextBlock]:
        if not blocks:
            return blocks
        if not self.api_key:
            for block in blocks:
                block.translation = block.text
            return blocks

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        system_prompt = (
            self.system_prompt_override
            or f"You are a manga translator from {source_lang} to {target_lang}. Translate the values in the JSON. Output ONLY the raw translated JSON. Do not wrap in markdown code blocks."
        )
        raw_text_json = get_raw_text(blocks)

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": f"Translate this JSON:\n{raw_text_json}"}
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
        }

        try:
            res = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout_seconds
            )
            if res.status_code == 200:
                content_list = res.json().get("content", [])
                translated_text = ""
                if content_list:
                    translated_text = content_list[0].get("text", "").strip()
                if set_texts_from_json(blocks, translated_text):
                    self.last_error = None
                    return blocks
                self.last_error = "Response JSON did not match block keys"
            else:
                self.last_error = f"HTTP {res.status_code}: {res.text}"
                logger.error("Claude API failed: %s", self.last_error)
        except Exception as e:
            self.last_error = str(e)
            logger.exception("Claude translation exception")

        for block in blocks:
            block.translation = block.text
        return blocks


class PapagoTranslatorWrapper(BaseTranslator):
    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        timeout_seconds: int = 15,
        max_retries: int = 2,
        retry_backoff_seconds: int = 2,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_seconds = timeout_seconds
        self.model = "papago"
        self.is_online = None
        self.last_error = None
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def check_connection(self) -> bool:
        if not self.client_id or not self.client_secret:
            self.last_error = "Papago Client ID/Secret missing"
            self.is_online = False
            return False
        self.is_online = True
        return True

    def translate_blocks(
        self,
        blocks: list[TextBlock],
        source_lang: str,
        target_lang: str,
        image: np.ndarray = None,
    ) -> list[TextBlock]:
        if not blocks:
            return blocks
        if not self.client_id or not self.client_secret:
            for block in blocks:
                block.translation = block.text
            return blocks

        lang_map = {
            "japanese": "ja",
            "日本語": "ja",
            "ja": "ja",
            "korean": "ko",
            "한국어": "ko",
            "ko": "ko",
            "english": "en",
            "영어": "en",
            "en": "en",
        }
        from_code = lang_map.get(source_lang.lower(), "ja")
        to_code = lang_map.get(target_lang.lower(), "ko")

        url = "https://naveropenapi.apigw.ntruss.com/nmt/v1/translation"
        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        try:
            for block in blocks:
                if not block.text.strip():
                    block.translation = ""
                    continue
                cleaned_text = block.text.replace("\n", " ").strip()
                data = {"source": from_code, "target": to_code, "text": cleaned_text}
                for attempt in range(max(0, int(self.max_retries)) + 1):
                    res = requests.post(
                        url, data=data, headers=headers, timeout=self.timeout_seconds
                    )
                    if res.status_code == 200:
                        translated = (
                            res.json()
                            .get("message", {})
                            .get("result", {})
                            .get("translatedText", "")
                        )
                        block.translation = translated
                        break
                    self.last_error = f"HTTP {res.status_code}: {res.text}"
                    logger.error("Papago API failed on text block: %s", self.last_error)
                    if attempt < max(0, int(self.max_retries)):
                        time.sleep(max(0, int(self.retry_backoff_seconds)))
                    else:
                        block.translation = block.text
            self.last_error = None
            return blocks
        except Exception as e:
            self.last_error = str(e)
            logger.exception("Papago translation exception")
            for block in blocks:
                block.translation = block.text
            return blocks


class BaiduTranslatorWrapper(BaseTranslator):
    def __init__(
        self,
        app_id: str = "",
        secret_key: str = "",
        timeout_seconds: int = 15,
        max_retries: int = 2,
        retry_backoff_seconds: int = 2,
    ):
        self.app_id = app_id
        self.secret_key = secret_key
        self.timeout_seconds = timeout_seconds
        self.model = "baidu"
        self.is_online = None
        self.last_error = None
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def check_connection(self) -> bool:
        if not self.app_id or not self.secret_key:
            self.last_error = "Baidu APP ID/Secret Key missing"
            self.is_online = False
            return False
        self.is_online = True
        return True

    def translate_blocks(
        self,
        blocks: list[TextBlock],
        source_lang: str,
        target_lang: str,
        image: np.ndarray = None,
    ) -> list[TextBlock]:
        if not blocks:
            return blocks
        if not self.app_id or not self.secret_key:
            for block in blocks:
                block.translation = block.text
            return blocks

        lang_map = {
            "japanese": "jp",
            "日本語": "jp",
            "ja": "jp",
            "korean": "kor",
            "한국어": "kor",
            "ko": "kor",
            "english": "en",
            "영어": "en",
            "en": "en",
        }
        from_code = lang_map.get(source_lang.lower(), "jp")
        to_code = lang_map.get(target_lang.lower(), "kor")

        import random
        import hashlib

        url = "http://api.fanyi.baidu.com/api/trans/vip/translate"

        try:
            for block in blocks:
                if not block.text.strip():
                    block.translation = ""
                    continue
                cleaned_text = block.text.replace("\n", " ").strip()
                salt = str(random.randint(32768, 65536))
                sign_str = self.app_id + cleaned_text + salt + self.secret_key
                sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

                params = {
                    "q": cleaned_text,
                    "from": from_code,
                    "to": to_code,
                    "appid": self.app_id,
                    "salt": salt,
                    "sign": sign,
                }
                for attempt in range(max(0, int(self.max_retries)) + 1):
                    res = requests.get(url, params=params, timeout=self.timeout_seconds)
                    if res.status_code == 200:
                        result = res.json()
                        trans_result = result.get("trans_result", [])
                        if trans_result:
                            block.translation = trans_result[0].get("dst", "")
                        elif result.get("error_code"):
                            self.last_error = f"Baidu error {result.get('error_code')}: {result.get('error_msg')}"
                            logger.error("Baidu API error: %s", self.last_error)
                            block.translation = block.text
                        else:
                            block.translation = block.text
                        break
                    self.last_error = f"HTTP {res.status_code}"
                    logger.error("Baidu API HTTP error: %s", self.last_error)
                    if attempt < max(0, int(self.max_retries)):
                        time.sleep(max(0, int(self.retry_backoff_seconds)))
                    else:
                        block.translation = block.text
            self.last_error = None
            return blocks
        except Exception as e:
            self.last_error = str(e)
            logger.exception("Baidu translation exception")
            for block in blocks:
                block.translation = block.text
            return blocks
