from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ...core.config import AppConfig
from ..job_messages import msg
from . import ModelDownloader, ModelID


MODEL_LABELS: dict[ModelID, tuple[str, str]] = {
    ModelID.RTDETR_V2_ONNX: ("Detection", "RT-DETRv2 FP32"),
    ModelID.RTDETR_INT8_ONNX: ("Detection", "RT-DETRv2 INT8"),
    ModelID.MANGA_OCR_MOBILE_ONNX: ("OCR", "Manga OCR Mobile ONNX"),
    ModelID.PPOCR_V5_DET_MOBILE: ("OCR", "PP-OCRv5 Mobile Detector"),
    ModelID.PPOCR_V5_REC_MOBILE: ("OCR", "PP-OCRv5 Chinese/Japanese Recognition"),
    ModelID.PPOCR_V5_REC_EN_MOBILE: ("OCR", "PP-OCRv5 English Recognition"),
    ModelID.PPOCR_V5_REC_KOREAN_MOBILE: ("OCR", "PP-OCRv5 Korean Recognition"),
    ModelID.LAMA_ONNX: ("Inpainting", "LaMa Manga ONNX"),
}


def _normalized(value: str | None) -> str:
    return (value or "").strip().lower()


def _append_unique(items: list[ModelID], model_ids: Iterable[ModelID]) -> None:
    for model_id in model_ids:
        if model_id not in items:
            items.append(model_id)


def _ppocr_recognition_model(source_language: str) -> ModelID:
    lang = _normalized(source_language)
    if lang in {"english", "en"}:
        return ModelID.PPOCR_V5_REC_EN_MOBILE
    if lang in {"korean", "ko", "한국어"}:
        return ModelID.PPOCR_V5_REC_KOREAN_MOBILE
    return ModelID.PPOCR_V5_REC_MOBILE


def get_required_model_ids(settings: AppConfig) -> list[ModelID]:
    cfg = settings
    required: list[ModelID] = []

    detect_model = _normalized(cfg.detect_model)
    if detect_model in {"small (int8)", "small (int8) [기본값]", "int8", "fast"}:
        _append_unique(required, [ModelID.RTDETR_INT8_ONNX])
    else:
        _append_unique(required, [ModelID.RTDETR_V2_ONNX])

    ocr_engine = _normalized(cfg.ocr_engine)
    source_language = cfg.source_language
    source_lang = _normalized(source_language)
    if ocr_engine in {"fast", "speed", "ppocr", "paddleocr", "paddle_ocr"}:
        _append_unique(required, [ModelID.PPOCR_V5_DET_MOBILE, _ppocr_recognition_model(source_language)])
    elif source_lang in {"japanese", "日本語", "ja"}:
        _append_unique(required, [ModelID.MANGA_OCR_MOBILE_ONNX])
    else:
        _append_unique(required, [ModelID.PPOCR_V5_DET_MOBILE, _ppocr_recognition_model(source_language)])

    inpaint_engine = _normalized(cfg.inpaint_engine)
    if inpaint_engine not in {"opencv", "fast", "speed", "telea"}:
        _append_unique(required, [ModelID.LAMA_ONNX])

    return required


def _model_item(model_id: ModelID) -> dict[str, Any]:
    category, label = MODEL_LABELS.get(model_id, ("Model", model_id.value))
    spec = ModelDownloader.registry.get(model_id)
    downloaded = ModelDownloader.is_downloaded(model_id) if spec else False
    return {
        "id": model_id.value,
        "category": category,
        "label": label,
        "downloaded": downloaded,
        "files": list(spec.files) if spec else [],
        "path": spec.save_dir if spec else "",
    }


def get_model_status(settings: AppConfig) -> dict[str, Any]:
    cfg = settings
    items = [_model_item(model_id) for model_id in get_required_model_ids(cfg)]
    missing = [item for item in items if not item["downloaded"]]
    return {
        "setup_completed": bool(cfg.setup_completed),
        "required": items,
        "missing": missing,
        "required_count": len(items),
        "missing_count": len(missing),
        "all_ready": not missing,
    }


def download_required_models(
    settings: AppConfig,
    job: dict[str, Any] | None = None,
    job_manager: Any | None = None,
) -> dict[str, Any]:
    cfg = settings
    ui_lang = cfg.ui_language if cfg else "en"
    model_ids = get_required_model_ids(cfg)
    total = len(model_ids)
    downloaded: list[str] = []
    already_present: list[str] = []

    report_progress = job is not None and job_manager is not None
    for index, model_id in enumerate(model_ids, start=1):
        if ModelDownloader.is_downloaded(model_id):
            already_present.append(model_id.value)
        else:
            category, label = MODEL_LABELS.get(model_id, ("Model", model_id.value))
            if report_progress:
                job_manager.update(
                    job,
                    progress=int(((index - 1) / max(total, 1)) * 95),
                    message=msg("download.downloading", ui_lang, name=label),
                )
            ModelDownloader.get(model_id)
            downloaded.append(model_id.value)

    if report_progress:
        job_manager.update(job, progress=95, message=msg("download.verifying", ui_lang))

    return {
        "downloaded": downloaded,
        "already_present": already_present,
        "status": get_model_status(cfg),
    }