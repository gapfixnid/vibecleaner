from __future__ import annotations

import importlib
import logging
from typing import Any

from app.version import APP_NAME


logger = logging.getLogger(APP_NAME)

_EXPORTS: dict[str, tuple[str, str]] = {
    "ProjectState": ("domain.project_state", "ProjectState"),
    "state": ("domain.project_state", "state"),
    "cache_executor": ("services.cache_service", "cache_executor"),
    "submit_cache_task": ("services.cache_service", "submit_cache_task"),
    "JPEG_QUALITY": ("services.image_encoding_service", "JPEG_QUALITY"),
    "PREVIEW_MAX_DIMENSION": ("services.image_encoding_service", "PREVIEW_MAX_DIMENSION"),
    "THUMBNAIL_WIDTH": ("services.image_encoding_service", "THUMBNAIL_WIDTH"),
    "encode_jpeg_bytes": ("services.image_encoding_service", "encode_jpeg_bytes"),
    "encode_png_bytes": ("services.image_encoding_service", "encode_png_bytes"),
    "encode_preview_bytes": ("services.image_encoding_service", "encode_preview_bytes"),
    "encode_preview_jpeg_bytes": ("services.image_encoding_service", "encode_preview_jpeg_bytes"),
    "encode_resized_jpeg_bytes": ("services.image_encoding_service", "encode_resized_jpeg_bytes"),
    "encode_resized_png_bytes": ("services.image_encoding_service", "encode_resized_png_bytes"),
    "encode_thumbnail_bytes": ("services.image_encoding_service", "encode_thumbnail_bytes"),
    "JobManager": ("services.job_service", "JobManager"),
    "job_manager": ("services.job_service", "job_manager"),
    "ensure_original_thumbnail": ("services.page_image_loader", "ensure_original_thumbnail"),
    "ensure_page_image": ("services.page_image_loader", "ensure_page_image"),
    "invalidate_page_caches": ("services.page_image_loader", "invalidate_page_caches"),
    "load_cv_image": ("services.page_image_loader", "load_cv_image"),
    "warm_original_thumbnail": ("services.page_image_loader", "warm_original_thumbnail"),
    "bubble_analysis_service": ("services.service_registry", "bubble_analysis_service"),
    "detection_service": ("services.service_registry", "detection_service"),
    "export_service": ("services.service_registry", "export_service"),
    "inpainting_service": ("services.service_registry", "inpainting_service"),
    "layout_planner_service": ("services.service_registry", "layout_planner_service"),
    "page_analysis_service": ("services.service_registry", "page_analysis_service"),
    "render_service": ("services.service_registry", "render_service"),
    "translation_service": ("services.service_registry", "translation_service"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'core' has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = ["logger", *_EXPORTS.keys()]
