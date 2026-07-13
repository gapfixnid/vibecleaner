import pytest
from types import SimpleNamespace

from backend.core.providers import (
    ConfigFieldSpec,
    ProviderCapabilities,
    ProviderManifest,
    ProviderRegistry,
    ProviderRequirements,
)


def _manifest(provider_id="test.ocr", **overrides):
    values = {
        "provider_id": provider_id,
        "display_name": "Test OCR",
        "stage": "ocr",
        "api_version": "1",
        "implementation_version": "1.0.0",
        "capabilities": ProviderCapabilities(
            languages={"ja", "ko"},
            devices={"cpu", "gpu"},
            execution_modes={"local"},
            features={"text", "vertical-text"},
            supports_batch=True,
        ),
        "resource_classes": {"cpu", "gpu"},
        "config_schema": (
            ConfigFieldSpec(
                key="model",
                value_type="enum",
                label="Model",
                choices=("small", "large"),
                default="small",
            ),
        ),
    }
    values.update(overrides)
    return ProviderManifest(**values)


def _adapter(provider_id):
    return SimpleNamespace(provider_id=provider_id, prepare=lambda runtime=None: None, shutdown=lambda: None)


def test_registry_registers_adapter_and_returns_deterministic_catalog():
    registry = ProviderRegistry()
    adapter = _adapter("z.ocr")
    registry.register(_manifest("z.ocr"), adapter)
    registry.register(_manifest("a.ocr"), _adapter("a.ocr"))

    catalog = registry.catalog()

    assert registry.get("z.ocr").adapter is adapter
    assert catalog["schema_version"] == 1
    assert [item["provider_id"] for item in catalog["providers"]] == ["a.ocr", "z.ocr"]
    assert catalog["providers"][0]["config_schema"][0]["choices"] == ["small", "large"]


def test_registry_rejects_duplicate_provider_ids():
    registry = ProviderRegistry()
    registry.register(_manifest(), _adapter("test.ocr"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(_manifest(), _adapter("test.ocr"))


def test_registry_rejects_adapter_with_a_different_id():
    registry = ProviderRegistry()

    with pytest.raises(ValueError, match="does not match"):
        registry.register(_manifest(), _adapter("other.ocr"))


def test_capability_resolver_filters_without_importing_concrete_engines():
    registry = ProviderRegistry()
    registry.register(_manifest(), _adapter("test.ocr"))
    registry.register(
        _manifest(
            "test.remote-ocr",
            capabilities=ProviderCapabilities(
                languages={"ja"},
                devices={"cpu"},
                execution_modes={"remote"},
                features={"text"},
            ),
            resource_classes={"network"},
        ),
        _adapter("test.remote-ocr"),
    )

    matches = registry.resolve(
        ProviderRequirements(
            stage="ocr",
            languages={"ja"},
            devices={"gpu"},
            execution_modes={"local"},
            features={"vertical-text"},
            resource_classes={"gpu"},
            requires_batch=True,
        )
    )

    assert [item.manifest.provider_id for item in matches] == ["test.ocr"]


def test_secret_config_fields_never_serialize_a_default():
    with pytest.raises(ValueError, match="cannot expose a default"):
        ConfigFieldSpec(key="api_key", value_type="secret", label="API key", default="secret")


def test_manifest_rejects_duplicate_config_keys():
    field = ConfigFieldSpec(key="model", value_type="string", label="Model")

    with pytest.raises(ValueError, match="duplicate config keys"):
        _manifest(config_schema=(field, field))
