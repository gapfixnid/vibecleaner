from fastapi import APIRouter, Depends

from ...core.container import AppContainer
from ..dependencies import get_container


router = APIRouter()


@router.get("/api/providers/catalog")
def get_provider_catalog(container: AppContainer = Depends(get_container)):
    """Return public provider metadata without runtime adapters or secrets."""
    return container.provider_registry.catalog()
