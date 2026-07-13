from fastapi import APIRouter, Depends

from ...core.container import AppContainer
from ..dependencies import get_container


router = APIRouter()


@router.get("/api/providers/catalog")
def get_provider_catalog(container: AppContainer = Depends(get_container)):
    """Return public provider metadata without runtime adapters or secrets."""
    return container.provider_registry.catalog()


@router.get("/api/providers/runtime")
def get_provider_runtime(container: AppContainer = Depends(get_container)):
    return {
        "translation": container.translation_service.get_diagnostics(),
        "inpainting": container.inpainting_service.runtime_status(),
    }
