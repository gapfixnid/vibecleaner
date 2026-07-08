import base64
import json
import logging
import re
import numpy as np
from engines.common.textblock import TextBlock
from infrastructure import image as imk

logger = logging.getLogger(__name__)


class TranslationParseError(ValueError):
    """Raised when a model response cannot be parsed as translation JSON."""


MODEL_MAP = {
    "Custom": "",  
    "Deepseek": "deepseek-v4-flash", 
    "GPT-4.1": "gpt-4.1",
    "GPT-4.1-mini": "gpt-4.1-mini",
    "Claude-4.6-Sonnet": "claude-sonnet-4-6",
    "Claude-4.5-Haiku": "claude-haiku-4-5-20251001",
    "Gemini-2.5-Flash-Lite": "gemini-2.5-flash-lite",
    "Gemini-3.1-Flash-Lite": "gemini-3.1-flash-lite",
    "Gemini-2.5-Pro": "gemini-2.5-pro"
}

def encode_image_array(img_array: np.ndarray):
    img_bytes = imk.encode_image(img_array, ".png")
    return base64.b64encode(img_bytes).decode('utf-8')

def get_raw_text(blk_list: list[TextBlock]):
    rw_txts_dict = {}
    for idx, blk in enumerate(blk_list):
        block_key = f"block_{idx}"
        rw_txts_dict[block_key] = blk.text
    
    raw_texts_json = json.dumps(rw_txts_dict, ensure_ascii=False, indent=4)
    
    return raw_texts_json

def get_raw_translation(blk_list: list[TextBlock]):
    rw_translations_dict = {}
    for idx, blk in enumerate(blk_list):
        block_key = f"block_{idx}"
        rw_translations_dict[block_key] = blk.translation
    
    raw_translations_json = json.dumps(rw_translations_dict, ensure_ascii=False, indent=4)
    
    return raw_translations_json

def extract_json_object(response_text: str) -> str:
    """Extract the first JSON object from noisy model output."""
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", response_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```(?:json|JSON)?", "", cleaned)
    cleaned = cleaned.replace("```", "")

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        snippet = cleaned[:500].replace("\n", "\\n")
        logger.warning("No JSON object found in translation response. snippet=%s", snippet)
        raise TranslationParseError("No JSON object found in translation response")
    return cleaned[start : end + 1]


def parse_translation_response(response_text: str) -> dict[str, str]:
    json_string = extract_json_object(response_text)
    try:
        parsed = json.loads(json_string, strict=False)
    except json.JSONDecodeError as exc:
        snippet = json_string[:500].replace("\n", "\\n")
        logger.exception("Failed to parse translation JSON. snippet=%s", snippet)
        raise TranslationParseError("Invalid translation JSON") from exc

    if not isinstance(parsed, dict):
        raise TranslationParseError("Translation JSON must be an object")
    return {str(key): "" if value is None else str(value) for key, value in parsed.items()}


def set_texts_from_json(blk_list: list[TextBlock], json_string: str) -> bool:
    translation_dict = parse_translation_response(json_string)
    applied = False

    for idx, blk in enumerate(blk_list):
        block_key = f"block_{idx}"
        if block_key in translation_dict:
            blk.translation = translation_dict[block_key]
            applied = True
        else:
            logger.warning("Translation JSON missing key: %s", block_key)
    return applied

def set_upper_case(blk_list: list[TextBlock], upper_case: bool):
    for blk in blk_list:
        translation = blk.translation
        if translation is None:
            continue
        if upper_case and not translation.isupper():
            blk.translation = translation.upper() 
        elif not upper_case and translation.isupper():
            blk.translation = translation.lower().capitalize()
        else:
            blk.translation = translation

def format_translations(blk_list: list[TextBlock], trg_lng_cd: str, upper_case: bool = True):
    for blk in blk_list:
        translation = blk.translation
        if translation is None:
            continue
        if upper_case and not translation.isupper():
            blk.translation = translation.upper()
        elif not upper_case and translation.isupper():
            blk.translation = translation.lower().capitalize()
        else:
            blk.translation = translation

def is_there_text(blk_list: list[TextBlock]) -> bool:
    return any(blk.text for blk in blk_list)
