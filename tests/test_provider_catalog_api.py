from types import SimpleNamespace

from backend.api.routes.catalog import get_provider_catalog
from backend.core.providers import ProviderRegistry
from backend.engines.provider_catalog import register_builtin_providers
from backend.main import create_app


def _builtin_registry():
    registry = ProviderRegistry()
    services = {
        "detection_service": object(),
        "translation_service": object(),
        "inpainting_service": object(),
        "render_service": object(),
    }
    register_builtin_providers(registry, **services)
    return registry, services


def test_builtin_catalog_registers_existing_runtime_adapters():
    registry, services = _builtin_registry()

    assert registry.get("builtin.detection.rtdetr-v2").adapter.service is services["detection_service"]
    assert registry.get("builtin.ocr.local").adapter.service is services["detection_service"]
    assert registry.get("builtin.translation.openai").adapter.service is services["translation_service"]
    assert {item.manifest.stage for item in registry.list()} == {
        "detection", "ocr", "translation", "inpainting", "rendering"
    }


def test_catalog_api_returns_metadata_without_adapters_or_secret_values():
    registry, _ = _builtin_registry()

    payload = get_provider_catalog(SimpleNamespace(provider_registry=registry))

    assert payload["schema_version"] == 1
    assert len(payload["providers"]) == 12
    assert all("adapter" not in provider for provider in payload["providers"])
    translation = next(item for item in payload["providers"] if item["provider_id"] == "builtin.translation.openai")
    secret = next(field for field in translation["config_schema"] if field["value_type"] == "secret")
    assert secret["default"] is None


def test_application_exposes_provider_catalog_route_and_registry():
    app = create_app()
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            route_paths.update(child.path for child in original_router.routes if hasattr(child, "path"))

    assert "/api/providers/catalog" in route_paths
    assert len(app.state.container.provider_registry.list()) == 12


def test_translation_catalog_has_one_manifest_per_legacy_selection_value():
    registry, _ = _builtin_registry()
    values = {
        item.manifest.selection_value
        for item in registry.list("translation")
    }

    assert values == {
        "google", "deepl", "openai", "claude", "papago", "baidu", "ollama", "openai_compatible"
    }


def test_translation_manifests_drive_provider_specific_configuration():
    registry, _ = _builtin_registry()
    by_value = {
        item.manifest.selection_value: item.manifest.to_dict()
        for item in registry.list("translation")
    }

    assert by_value["google"]["config_schema"] == []
    openai_fields = {field["key"]: field for field in by_value["openai"]["config_schema"]}
    assert openai_fields["translation_api_key"]["value_type"] == "secret"
    assert openai_fields["translation_api_key"]["default"] is None
    assert openai_fields["translation_model"]["value_type"] == "model"
    assert "model-requires-key" in by_value["openai"]["capabilities"]["features"]
    papago_fields = {field["key"]: field for field in by_value["papago"]["config_schema"]}
    assert papago_fields["translation_api_base_url"]["label"] == "settings.papagoClientId"
    assert papago_fields["translation_api_key"]["placeholder"] == "settings.papagoClientSecretPlaceholder"
