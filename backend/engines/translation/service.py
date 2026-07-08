import os
import json
import logging
import threading
import hashlib
import shutil
import numpy as np
from typing import List, Optional, Any, Dict, cast
from infrastructure.storage import get_app_data_dir
from modules.config import OLLAMA_API_URL
from .providers import (
    OllamaTranslator,
    OpenAICompatibleTranslator,
    GoogleTranslatorWrapper,
    DeepLTranslatorWrapper,
    OpenAITranslatorWrapper,
    ClaudeTranslatorWrapper,
    PapagoTranslatorWrapper,
    BaiduTranslatorWrapper
)
from .base import BaseTranslator

logger = logging.getLogger(__name__)


class TranslationService:
    _TM_CACHE_MAX = 10000

    def __init__(self, config, translator: Optional[BaseTranslator] = None) -> None:
        self.config = config
        configured_translator = translator or self._build_configured_translator()
        self.translators: Dict[str, BaseTranslator] = {self.config.translation_provider: configured_translator}
        self.active_translator_name: str = self.config.translation_provider
        self._cache: Dict[str, str] = {}  # In-memory translation cache (src_text -> translated_text)
        self._cache_lock = threading.RLock()
        self._translator_lock = threading.RLock()

        # Save TM and system prompt in user's AppData directory to prevent permission issues
        app_data_dir = get_app_data_dir()
        self.tm_path = os.path.join(app_data_dir, "translation_memory.json")
        self.system_prompt_path = os.path.join(app_data_dir, "system_prompt.txt")

        # Load Translation Memory (TM) on startup
        self._load_tm()

        # Load custom system prompt override
        self._load_system_prompt()

    @property
    def system_prompt(self) -> str:
        override = getattr(self.translator, "system_prompt_override", None)
        if isinstance(override, str) and override:
            return override
        return ""

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self.save_system_prompt(value)

    def _load_system_prompt(self) -> None:
        if os.path.exists(self.system_prompt_path):
            try:
                with open(self.system_prompt_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content:
                    for t in self.translators.values():
                        if hasattr(t, "system_prompt_override"):
                            t.system_prompt_override = content
                logger.info("Loaded system prompt override from %s", self.system_prompt_path)
            except Exception:
                logger.exception("Failed to load system prompt from %s", self.system_prompt_path)

    def save_system_prompt(self, prompt: str) -> bool:
        for t in self.translators.values():
            if hasattr(t, "system_prompt_override"):
                t.system_prompt_override = prompt
        try:
            with open(self.system_prompt_path, "w", encoding="utf-8") as f:
                f.write(prompt)
            logger.info("Saved system prompt override to %s", self.system_prompt_path)
            return True
        except Exception:
            logger.exception("Failed to save system prompt to %s", self.system_prompt_path)
            return False

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()
            self._save_tm()
        logger.info("Cleared translation memory cache")

    @property
    def translator(self) -> Any:
        """Dynamically references the active translator (for backward compatibility)."""
        return self.translators[self.active_translator_name]

    def reload(self) -> None:
        """Rebuild the active translator from the current settings.

        Must be called after settings change so provider/model/API key/timeout
        updates take effect without an app restart.
        """
        with self._translator_lock:
            override = self.system_prompt  # preserve any custom prompt
            provider = self.config.translation_provider
            new_translator = self._build_configured_translator()
            if override and hasattr(new_translator, "system_prompt_override"):
                new_translator.system_prompt_override = override
            self.translators[provider] = new_translator
            self.active_translator_name = provider
        logger.info("Translation service reloaded (provider=%s)", provider)

    def _build_configured_translator(self) -> BaseTranslator:
        config = self.config
        provider = (config.translation_provider or "google").lower()
        if provider == "google":
            return GoogleTranslatorWrapper(
                max_retries=int(config.translation_max_retries),
                retry_backoff_seconds=int(config.translation_retry_backoff_seconds),
            )
        elif provider == "deepl":
            return DeepLTranslatorWrapper(
                api_key=config.translation_api_key,
                timeout_seconds=int(config.translation_timeout_seconds),
                max_retries=int(config.translation_max_retries),
                retry_backoff_seconds=int(config.translation_retry_backoff_seconds),
            )
        elif provider == "openai":
            return OpenAITranslatorWrapper(
                api_key=config.translation_api_key,
                model=config.translation_model or "gpt-4o-mini",
                timeout_seconds=int(config.translation_timeout_seconds),
                supports_vision=bool(config.translation_supports_vision),
                temperature=float(config.translation_llm_temperature),
                top_p=float(config.translation_llm_top_p),
                max_tokens=int(config.translation_llm_max_tokens),
                max_retries=int(config.translation_max_retries),
                retry_backoff_seconds=int(config.translation_retry_backoff_seconds),
            )
        elif provider == "claude":
            return ClaudeTranslatorWrapper(
                api_key=config.translation_api_key,
                model=config.translation_model or "claude-3-5-sonnet-20241022",
                timeout_seconds=int(config.translation_timeout_seconds),
                supports_vision=bool(config.translation_supports_vision),
                temperature=float(config.translation_llm_temperature),
                top_p=float(config.translation_llm_top_p),
                max_tokens=int(config.translation_llm_max_tokens),
            )
        elif provider == "papago":
            return PapagoTranslatorWrapper(
                client_id=config.translation_api_base_url,
                client_secret=config.translation_api_key,
                timeout_seconds=int(config.translation_timeout_seconds),
                max_retries=int(config.translation_max_retries),
                retry_backoff_seconds=int(config.translation_retry_backoff_seconds),
            )
        elif provider == "baidu":
            return BaiduTranslatorWrapper(
                app_id=config.translation_api_base_url,
                secret_key=config.translation_api_key,
                timeout_seconds=int(config.translation_timeout_seconds),
                max_retries=int(config.translation_max_retries),
                retry_backoff_seconds=int(config.translation_retry_backoff_seconds),
            )
        elif provider in {"openai_compatible", "openai-compatible", "llamacpp", "llama.cpp", "lmstudio", "lm_studio"}:
            return OpenAICompatibleTranslator(
                api_url=config.translation_api_base_url,
                model=config.translation_model or "local-model",
                api_key=config.translation_api_key,
                timeout_seconds=int(config.translation_timeout_seconds),
                supports_vision=bool(config.translation_supports_vision),
                temperature=float(config.translation_llm_temperature),
                top_p=float(config.translation_llm_top_p),
                max_tokens=int(config.translation_llm_max_tokens),
                max_retries=int(config.translation_max_retries),
                retry_backoff_seconds=int(config.translation_retry_backoff_seconds),
            )
        return OllamaTranslator(
            api_url=OLLAMA_API_URL,
            model=config.translation_model or "llama3",
            supports_vision=bool(config.translation_supports_vision),
            temperature=float(config.translation_llm_temperature),
            top_p=float(config.translation_llm_top_p),
            max_tokens=int(config.translation_llm_max_tokens),
            max_retries=int(config.translation_max_retries),
            retry_backoff_seconds=int(config.translation_retry_backoff_seconds),
        )

    @property
    def model(self) -> str:
        return cast(str, self.translator.model)

    @model.setter
    def model(self, value: str) -> None:
        self.translator.model = value

    def check_connection(self) -> bool:
        return cast(bool, self.translator.check_connection())

    @property
    def installed_models(self) -> List[str]:
        return cast(List[str], self.translator.installed_models)

    def translate_blocks(self, blocks: List[Any], src_lang: str, tgt_lang: str, cv_image: np.ndarray) -> None:
        # Filter blocks based on translation cache
        to_translate = []
        block_cache_keys: dict[int, str] = {}
        with self._cache_lock:
            for idx, block in enumerate(blocks):
                cache_key = self._cache_key(blocks, idx)
                block_cache_keys[id(block)] = cache_key
                if self.config.translation_cache_enabled and cache_key in self._cache:
                    block.translation = self._cache[cache_key]
                else:
                    to_translate.append(block)

        # Call active translator for untranslated blocks
        if to_translate:
            with self._translator_lock:
                self.translator.translate_blocks(to_translate, src_lang, tgt_lang, cv_image)

            # Cache the newly translated text blocks and save to Translation Memory file
            with self._cache_lock:
                for block in to_translate:
                    translation = cast(str, getattr(block, "translation", ""))
                    if self.config.translation_cache_enabled and translation:
                        self._cache[block_cache_keys[id(block)]] = translation
                # Bound the in-memory TM (FIFO) to avoid unbounded growth.
                if len(self._cache) > self._TM_CACHE_MAX:
                    for old_key in list(self._cache.keys())[: len(self._cache) - self._TM_CACHE_MAX]:
                        self._cache.pop(old_key, None)
                self._save_tm()

    def _cache_key(self, blocks: List[Any], index: int) -> str:
        text = cast(str, blocks[index].text).strip()
        if self.config.translation_cache_mode != "text_with_context":
            return text

        neighbor_parts = []
        for offset in (-1, 1):
            neighbor_index = index + offset
            if 0 <= neighbor_index < len(blocks):
                neighbor_parts.append(blocks[neighbor_index].text.strip())
        prompt = self.system_prompt or ""
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        raw_key = {
            "text": text,
            "neighbors": neighbor_parts,
            "model": str(self.model),
            "prompt_hash": prompt_hash,
        }
        return (
            "ctx:" + hashlib.sha256(json.dumps(raw_key, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        )

    def delete_cache_entry(self, key: str) -> bool:
        with self._cache_lock:
            existed = key in self._cache
            self._cache.pop(key, None)
            self._save_tm()
            return existed

    def export_translation_memory(self, destination_path: str) -> None:
        with self._cache_lock:
            self._save_tm()
        shutil.copyfile(self.tm_path, destination_path)

    def import_translation_memory(self, source_path: str, merge: bool = True) -> None:
        with open(source_path, "r", encoding="utf-8") as f:
            imported = json.load(f)
        if not isinstance(imported, dict):
            raise ValueError("Translation memory file must contain a JSON object")
        with self._cache_lock:
            if merge:
                self._cache.update({str(k): str(v) for k, v in imported.items()})
            else:
                self._cache = {str(k): str(v) for k, v in imported.items()}
            self._save_tm()

    def get_diagnostics(self) -> dict[str, Any]:
        translator = self.translator
        return {
            "provider": self.active_translator_name,
            "model": self.model,
            "connected": getattr(translator, "is_online", None),
            "last_error": getattr(translator, "last_error", None),
            "cache_enabled": self.config.translation_cache_enabled,
            "cache_mode": self.config.translation_cache_mode,
            "cache_entries": len(self._cache),
        }

    def _load_tm(self) -> None:
        """Load persistent Translation Memory from local JSON file."""
        if os.path.exists(self.tm_path):
            try:
                with self._cache_lock:
                    with open(self.tm_path, "r", encoding="utf-8") as f:
                        self._cache = json.load(f)
                logger.info("Loaded %d translation memory records from %s", len(self._cache), self.tm_path)
            except Exception:
                logger.exception("Failed to load translation memory from %s", self.tm_path)

    def _save_tm(self) -> None:
        """Save persistent Translation Memory to local JSON file."""
        try:
            with self._cache_lock:
                with open(self.tm_path, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, ensure_ascii=False, indent=4)
        except Exception:
            logger.exception("Failed to save translation memory to %s", self.tm_path)
