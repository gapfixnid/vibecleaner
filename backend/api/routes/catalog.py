from fastapi import APIRouter, Depends

from ...core.container import AppContainer
from ..dependencies import get_container
from ...pipeline.telemetry import DEFAULT_TELEMETRY_FILENAME, load_telemetry, summarize_telemetry
from ...infrastructure.storage import get_app_data_dir
import os


router = APIRouter()


@router.get("/api/providers/catalog")
def get_provider_catalog(container: AppContainer = Depends(get_container)):
    """Return public provider metadata without runtime adapters or secrets."""
    return container.provider_registry.catalog()


@router.get("/api/providers/runtime")
def get_provider_runtime(container: AppContainer = Depends(get_container)):
    return {
        "detection": container.detection_service.get_diagnostics(),
        "translation": container.translation_service.get_diagnostics(),
        "inpainting": container.inpainting_service.runtime_status(),
    }


@router.get("/api/pipeline/telemetry")
def get_pipeline_telemetry(container: AppContainer = Depends(get_container)):
    path = getattr(container.config, "pipeline_telemetry_path", None)
    if not path:
        path = os.path.join(get_app_data_dir(), DEFAULT_TELEMETRY_FILENAME)
    return summarize_telemetry(load_telemetry(path))
