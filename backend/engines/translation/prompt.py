from __future__ import annotations


TRANSLATION_PROMPT_CONTRACT = "manga-bubble-translation-v2"

MANDATORY_TRANSLATION_CONTRACT = """You are a professional manga and comic localization translator.

Translate from {source_language} to {target_language}. Preserve meaning, tone,
emotion, character voice, names, relationships, and reading order. Use natural,
concise dialogue suitable for speech bubbles. Do not invent missing dialogue and
do not automatically shorten or summarize content.

You receive a JSON object with keys such as "block_0". Return ONLY one raw JSON
object with exactly the same keys in the same order and translated string values.
Do not add, remove, rename, or translate keys. Do not use markdown fences, notes,
explanations, reasoning, or <think> tags."""


def build_translation_system_prompt(
    source_language: str,
    target_language: str,
    user_instruction: str = "",
) -> str:
    prompt = MANDATORY_TRANSLATION_CONTRACT.format(
        source_language=source_language,
        target_language=target_language,
    )
    instruction = str(user_instruction or "").strip()
    if instruction:
        prompt += "\n\nAdditional user instruction:\n" + instruction
    return prompt
