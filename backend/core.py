import logging

from app.qt_runtime import qt_app  # noqa: F401
from app.version import APP_NAME
from domain.project_state import ProjectState, state
from services.cache_service import cache_executor, submit_cache_task
from services.image_encoding_service import (
    JPEG_QUALITY,
    PREVIEW_MAX_DIMENSION,
    THUMBNAIL_WIDTH,
    encode_jpeg_bytes,
    encode_png_bytes,
    encode_preview_bytes,
    encode_preview_jpeg_bytes,
    encode_resized_jpeg_bytes,
    encode_resized_png_bytes,
    encode_thumbnail_bytes,
)
from services.job_service import JobManager, job_manager
from services.page_image_loader import (
    ensure_original_thumbnail,
    ensure_page_image,
    invalidate_page_caches,
    load_cv_image,
    warm_original_thumbnail,
)
from services.service_registry import (
    bubble_analysis_service,
    detection_service,
    export_service,
    inpainting_service,
    layout_planner_service,
    page_analysis_service,
    render_service,
    translation_service,
)


logger = logging.getLogger(APP_NAME)
