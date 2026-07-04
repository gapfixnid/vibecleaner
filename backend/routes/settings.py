import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from modules.config import config, OLLAMA_API_URL
from core import logger, translation_service

router = APIRouter()

class SettingsSchema(BaseModel):
    translation_model: str
    translation_provider: str
    translation_api_base_url: str
    translation_api_key: str
    translation_api_key_configured: bool = False
    translation_timeout_seconds: int
    translation_supports_vision: bool
    translation_cache_enabled: bool = True
    translation_cache_mode: str = "text_with_context"
    translation_max_retries: int = 2
    translation_retry_backoff_seconds: int = 2
    translation_llm_temperature: float = 0.1
    translation_llm_top_p: float = 0.95
    translation_llm_max_tokens: int = 4096
    ui_language: str = "en"
    source_language: str
    target_language: str
    system_prompt: str
    detect_model: str
    confidence_threshold: float
    tiling_enabled: bool
    bubbles_only: bool
    min_font_size: float
    max_font_size: float
    default_font_size: float
    inpaint_mask_dilation: int
    inpaint_use_textbox_only: bool
    inpaint_clip_to_bubble: bool

@router.get("/api/settings")
def get_settings():
    return {
        "translation_model": config.translation_model,
        "translation_provider": config.translation_provider,
        "translation_api_base_url": config.translation_api_base_url,
        "translation_api_key": "",
        "translation_api_key_configured": bool(config.translation_api_key),
        "translation_timeout_seconds": config.translation_timeout_seconds,
        "translation_supports_vision": config.translation_supports_vision,
        "translation_cache_enabled": config.translation_cache_enabled,
        "translation_cache_mode": config.translation_cache_mode,
        "translation_max_retries": config.translation_max_retries,
        "translation_retry_backoff_seconds": config.translation_retry_backoff_seconds,
        "translation_llm_temperature": config.translation_llm_temperature,
        "translation_llm_top_p": config.translation_llm_top_p,
        "translation_llm_max_tokens": config.translation_llm_max_tokens,
        "ui_language": config.ui_language,
        "source_language": config.source_language,
        "target_language": config.target_language,
        "system_prompt": translation_service.system_prompt or config.system_prompt,
        "detect_model": config.detect_model,
        "confidence_threshold": config.confidence_threshold,
        "tiling_enabled": config.tiling_enabled,
        "bubbles_only": config.bubbles_only,
        "min_font_size": config.min_font_size,
        "max_font_size": config.max_font_size,
        "default_font_size": config.default_font_size,
        "inpaint_mask_dilation": config.inpaint_mask_dilation,
        "inpaint_use_textbox_only": config.inpaint_use_textbox_only,
        "inpaint_clip_to_bubble": config.inpaint_clip_to_bubble,
    }

@router.post("/api/settings")
def update_settings(settings: SettingsSchema):
    config.translation_model = settings.translation_model
    config.translation_provider = settings.translation_provider
    config.translation_api_base_url = settings.translation_api_base_url
    if settings.translation_api_key:
        config.translation_api_key = settings.translation_api_key
    elif not settings.translation_api_key_configured:
        config.translation_api_key = ""
    config.translation_timeout_seconds = settings.translation_timeout_seconds
    config.translation_supports_vision = settings.translation_supports_vision
    config.translation_cache_enabled = settings.translation_cache_enabled
    config.translation_cache_mode = settings.translation_cache_mode
    config.translation_max_retries = settings.translation_max_retries
    config.translation_retry_backoff_seconds = settings.translation_retry_backoff_seconds
    config.translation_llm_temperature = settings.translation_llm_temperature
    config.translation_llm_top_p = settings.translation_llm_top_p
    config.translation_llm_max_tokens = settings.translation_llm_max_tokens
    config.ui_language = settings.ui_language
    config.source_language = settings.source_language
    config.target_language = settings.target_language
    config.system_prompt = settings.system_prompt
    config.detect_model = settings.detect_model
    config.confidence_threshold = settings.confidence_threshold
    config.tiling_enabled = settings.tiling_enabled
    config.bubbles_only = settings.bubbles_only
    config.min_font_size = settings.min_font_size
    config.max_font_size = settings.max_font_size
    config.default_font_size = settings.default_font_size
    config.inpaint_mask_dilation = settings.inpaint_mask_dilation
    config.inpaint_use_textbox_only = settings.inpaint_use_textbox_only
    config.inpaint_clip_to_bubble = settings.inpaint_clip_to_bubble

    # Persist and apply the prompt override before rebuilding the translator so
    # the newly-created provider instance receives the current prompt.
    try:
        translation_service.system_prompt = settings.system_prompt
    except Exception:
        logger.exception("Failed to apply translation system prompt after settings update")

    # Rebuild the active translator so provider/model/key/timeout changes apply
    # without an app restart.
    try:
        translation_service.reload()
    except Exception:
        logger.exception("Failed to reload translation service after settings update")

    success = config.save()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save settings")
    return get_settings()

@router.get("/api/ollama/models")
def get_ollama_models():
    """Retrieve available local models from Ollama api."""
    return {"models": _fetch_ollama_models()}


class ModelListRequest(BaseModel):
    provider: str
    api_key: str = ""
    base_url: str = ""


_OPENAI_EXCLUDE = ("embedding", "audio", "realtime", "transcribe", "tts", "image", "moderation", "whisper", "dall-e")


def _fetch_ollama_models() -> list[str]:
    import requests
    try:
        res = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=3.0)
        if res.status_code == 200:
            return [m["name"] for m in res.json().get("models", [])]
    except Exception as e:
        logger.warning("Failed to connect to Ollama: %s", e)
    return []


def _fetch_openai_models(api_key: str) -> list[str]:
    if not api_key:
        return []
    import requests
    res = requests.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=8.0,
    )
    if res.status_code in (401, 403):
        raise ValueError("API 키가 유효하지 않습니다.")
    res.raise_for_status()
    ids = [m.get("id", "") for m in res.json().get("data", [])]
    chat = [i for i in ids if i.startswith("gpt-") and not any(x in i for x in _OPENAI_EXCLUDE)]
    return sorted(chat)


def _fetch_anthropic_models(api_key: str) -> list[str]:
    if not api_key:
        return []
    import requests
    res = requests.get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        timeout=8.0,
    )
    if res.status_code in (401, 403):
        raise ValueError("API 키가 유효하지 않습니다.")
    res.raise_for_status()
    return [m.get("id", "") for m in res.json().get("data", []) if m.get("id")]


def _fetch_openai_compatible_models(base_url: str, api_key: str) -> list[str]:
    if not base_url:
        return []
    _validate_openai_compatible_base_url(base_url)
    import requests
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    res = requests.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=8.0)
    res.raise_for_status()
    return sorted(m.get("id", "") for m in res.json().get("data", []) if m.get("id"))


def _validate_openai_compatible_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Base URL은 http 또는 https URL이어야 합니다.")
    if parsed.username or parsed.password:
        raise ValueError("Base URL에는 사용자 정보가 포함될 수 없습니다.")

    host = parsed.hostname.lower()
    if host == "localhost":
        return

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if parsed.scheme == "http":
            raise ValueError("HTTP Base URL은 localhost 또는 사설 네트워크 주소만 사용할 수 있습니다.")
        return

    if ip.is_loopback:
        return
    if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        raise ValueError("Base URL 주소가 허용되지 않는 네트워크 범위입니다.")
    if ip.is_private:
        return
    if parsed.scheme == "http":
        raise ValueError("공개 네트워크 Base URL은 https를 사용해야 합니다.")


@router.post("/api/translation/models")
def get_translation_models(req: ModelListRequest):
    """List models for the selected provider using the supplied credentials.

    Returns {provider, models, error?}. Empty models with no error means the
    provider has no model concept or credentials are not yet entered.
    """
    provider = (req.provider or "").lower()
    try:
        if provider == "ollama":
            models = _fetch_ollama_models()
        elif provider == "openai":
            models = _fetch_openai_models(req.api_key)
        elif provider == "claude":
            models = _fetch_anthropic_models(req.api_key)
        elif provider in {"openai_compatible", "openai-compatible", "llamacpp", "llama.cpp", "lmstudio", "lm_studio"}:
            models = _fetch_openai_compatible_models(req.base_url, req.api_key)
        else:
            models = []
        return {"provider": provider, "models": models}
    except ValueError as e:
        return {"provider": provider, "models": [], "error": str(e)}
    except Exception as e:
        logger.warning("Failed to list models for provider=%s: %s", provider, e)
        return {"provider": provider, "models": [], "error": "모델 목록을 불러오지 못했습니다."}
