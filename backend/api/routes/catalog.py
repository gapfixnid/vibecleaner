from fastapi import APIRouter, Depends

from ...core.container import AppContainer
from ..dependencies import get_container
from ...pipeline.telemetry import DEFAULT_TELEMETRY_FILENAME, load_telemetry, summarize_telemetry
from ...infrastructure.storage import get_app_data_dir
from ...infrastructure.model_catalog import list_supported_models
import os


router = APIRouter()


@router.get("/api/providers/catalog")
def get_provider_catalog(container: AppContainer = Depends(get_container)):
    """Return public provider metadata without runtime adapters or secrets."""
    catalog = container.provider_registry.catalog()
    options_by_stage = list_supported_models()
    field_by_stage = {
        "detection": "detect_model",
        "ocr": "ocr_model",
        "inpainting": "inpaint_engine",
    }
    for provider in catalog["providers"]:
        stage = provider.get("stage")
        field_key = field_by_stage.get(stage)
        if not field_key:
            continue
        options = options_by_stage[stage]
        for field in provider.get("config_schema", []):
            if field.get("key") == field_key:
                field["choices"] = [option.id for option in options]
                field["choice_labels"] = [option.label for option in options]
                break
        provider["model_catalog"] = [
            {
                "selection_value": option.id,
                "display_name": option.label,
                "quality_score": 0.0,
                "speed_score": 0.0,
                "resource_classes": ["cpu", "gpu"],
            }
            for option in options
        ]
    return catalog


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
