"""Language- and engine-specific OCR crop preprocessing defaults."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrPreprocessingProfile:
    padding: int
    crop_scale: float
    adaptive_binarization: bool
    adaptive_binarization_strength: float


_BASE_PROFILE = OcrPreprocessingProfile(8, 1.5, True, 2.0)
_PROFILES = {
    ("japanese", "manga_ocr"): _BASE_PROFILE,
    ("japanese", "ppocr"): _BASE_PROFILE,
    ("english", "ppocr"): OcrPreprocessingProfile(6, 1.25, True, 1.5),
    ("korean", "ppocr"): OcrPreprocessingProfile(8, 1.4, True, 2.0),
}


def normalize_language(language: str | None) -> str:
    value = str(language or "Japanese").strip().lower()
    if value in {"japanese", "日本語", "ja"}:
        return "japanese"
    if value in {"english", "영어", "en"}:
        return "english"
    if value in {"korean", "한국어", "ko"}:
        return "korean"
    return value


def normalize_engine(engine: str | None, language: str | None = None) -> str:
    value = str(engine or "auto").strip().lower()
    if value in {"manga_ocr", "manga-ocr", "manga", "manga_ocr_mobile"}:
        return "manga_ocr"
    if value in {"ppocr", "paddleocr", "paddle_ocr", "fast", "speed"}:
        return "ppocr"
    if value in {"balanced", "standard", "auto"}:
        return "manga_ocr" if normalize_language(language) == "japanese" else "ppocr"
    return "manga_ocr" if normalize_language(language) == "japanese" else "ppocr"


def resolve_ocr_preprocessing_profile(
    language: str | None,
    engine: str | None,
    *,
    padding: int | None = None,
    crop_scale: float | None = None,
    adaptive_binarization: bool | None = None,
    adaptive_binarization_strength: float | None = None,
) -> OcrPreprocessingProfile:
    """Resolve defaults while allowing every explicit caller override."""
    language_name = normalize_language(language)
    engine_name = normalize_engine(engine, language_name)
    base = _PROFILES.get((language_name, engine_name), _BASE_PROFILE)
    return OcrPreprocessingProfile(
        padding=int(base.padding if padding is None else padding),
        crop_scale=float(base.crop_scale if crop_scale is None else crop_scale),
        adaptive_binarization=bool(
            base.adaptive_binarization if adaptive_binarization is None else adaptive_binarization
        ),
        adaptive_binarization_strength=float(
            base.adaptive_binarization_strength
            if adaptive_binarization_strength is None
            else adaptive_binarization_strength
        ),
    )
