"""Stable provider metadata shared by the composition root and API catalog."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal


ProviderStage = Literal["detection", "ocr", "translation", "inpainting", "rendering"]
ResourceClass = Literal["cpu", "gpu", "io", "network"]
ConfigValueType = Literal["string", "integer", "number", "boolean", "enum", "secret", "model"]

VALID_STAGES = frozenset({"detection", "ocr", "translation", "inpainting", "rendering"})
VALID_RESOURCES = frozenset({"cpu", "gpu", "io", "network"})
VALID_CONFIG_TYPES = frozenset({"string", "integer", "number", "boolean", "enum", "secret", "model"})
_PROVIDER_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True)
class ProviderModelProfile:
    """Selectable model/profile metadata used by adaptive quality routing."""

    selection_value: str
    display_name: str
    quality_score: float
    latency_score: float
    resource_classes: frozenset[ResourceClass] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.selection_value.strip() or not self.display_name.strip():
            raise ValueError("Provider model profile requires a selection value and display name")
        if not 0.0 <= self.quality_score <= 1.0 or not 0.0 <= self.latency_score <= 1.0:
            raise ValueError("Provider model scores must be between 0 and 1")
        resources = frozenset(self.resource_classes)
        if not resources or not resources.issubset(VALID_RESOURCES):
            raise ValueError(f"Invalid model resource classes: {sorted(resources)!r}")
        object.__setattr__(self, "resource_classes", resources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_value": self.selection_value,
            "display_name": self.display_name,
            "quality_score": self.quality_score,
            "latency_score": self.latency_score,
            "resource_classes": sorted(self.resource_classes),
        }


@dataclass(frozen=True)
class ConfigFieldSpec:
    key: str
    value_type: ConfigValueType
    label: str
    required: bool = False
    default: Any = None
    choices: tuple[str, ...] = ()
    choice_labels: tuple[str, ...] = ()
    advanced: bool = True
    placeholder: str | None = None
    help_text: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    visible_when_key: str | None = None
    visible_when_value: Any = True

    def __post_init__(self) -> None:
        if not self.key or not self.key.replace("_", "").isalnum():
            raise ValueError(f"Invalid provider config key: {self.key!r}")
        if self.value_type not in VALID_CONFIG_TYPES:
            raise ValueError(f"Unsupported provider config type: {self.value_type!r}")
        object.__setattr__(self, "choices", tuple(self.choices))
        object.__setattr__(self, "choice_labels", tuple(self.choice_labels))
        if self.value_type == "enum" and not self.choices:
            raise ValueError(f"Enum provider config field {self.key!r} requires choices")
        if self.value_type == "enum" and self.default is not None and self.default not in self.choices:
            raise ValueError(f"Enum provider config field {self.key!r} default must be one of its choices")
        if self.value_type != "enum" and self.choices:
            raise ValueError(f"Only enum provider config fields may declare choices: {self.key!r}")
        if self.choice_labels and len(self.choice_labels) != len(self.choices):
            raise ValueError(f"Provider config field {self.key!r} choice labels must match choices")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"Provider config field {self.key!r} minimum exceeds maximum")
        if self.step is not None and self.step <= 0:
            raise ValueError(f"Provider config field {self.key!r} step must be positive")
        if self.value_type == "secret" and self.default not in (None, ""):
            raise ValueError(f"Secret provider config field {self.key!r} cannot expose a default")

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value_type": self.value_type,
            "label": self.label,
            "required": self.required,
            "default": None if self.value_type == "secret" else self.default,
            "choices": list(self.choices),
            "choice_labels": list(self.choice_labels),
            "advanced": self.advanced,
            "placeholder": self.placeholder,
            "help_text": self.help_text,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "visible_when_key": self.visible_when_key,
            "visible_when_value": self.visible_when_value,
        }


@dataclass(frozen=True)
class ProviderCapabilities:
    languages: frozenset[str] = field(default_factory=frozenset)
    devices: frozenset[str] = field(default_factory=lambda: frozenset({"cpu"}))
    execution_modes: frozenset[str] = field(default_factory=frozenset)
    features: frozenset[str] = field(default_factory=frozenset)
    supports_batch: bool = False

    def __post_init__(self) -> None:
        for name in ("languages", "devices", "execution_modes", "features"):
            values = frozenset(str(value) for value in getattr(self, name))
            if any(not value for value in values):
                raise ValueError(f"Provider capability {name} contains an empty value")
            object.__setattr__(self, name, values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "languages": sorted(self.languages),
            "devices": sorted(self.devices),
            "execution_modes": sorted(self.execution_modes),
            "features": sorted(self.features),
            "supports_batch": self.supports_batch,
        }


@dataclass(frozen=True)
class ProviderManifest:
    provider_id: str
    display_name: str
    stage: ProviderStage
    api_version: str
    implementation_version: str
    capabilities: ProviderCapabilities
    resource_classes: frozenset[ResourceClass]
    max_concurrency: int = 1
    queue_capacity: int = 0
    config_schema: tuple[ConfigFieldSpec, ...] = ()
    legacy_adapter: bool = False
    selection_value: str | None = None
    description: str = ""
    catalog_order: int = 100
    model_catalog: tuple[ProviderModelProfile, ...] = ()

    def __post_init__(self) -> None:
        if not _PROVIDER_ID.fullmatch(self.provider_id):
            raise ValueError(f"Invalid provider_id: {self.provider_id!r}")
        if not self.display_name.strip():
            raise ValueError("Provider display_name is required")
        if self.stage not in VALID_STAGES:
            raise ValueError(f"Unsupported provider stage: {self.stage!r}")
        if not self.api_version or not self.implementation_version:
            raise ValueError("Provider API and implementation versions are required")
        resources = frozenset(self.resource_classes)
        if not resources or not resources.issubset(VALID_RESOURCES):
            raise ValueError(f"Invalid provider resource classes: {sorted(resources)!r}")
        object.__setattr__(self, "resource_classes", resources)
        object.__setattr__(self, "config_schema", tuple(self.config_schema))
        object.__setattr__(self, "model_catalog", tuple(self.model_catalog))
        if self.max_concurrency < 1:
            raise ValueError("Provider max_concurrency must be positive")
        if self.queue_capacity < 0:
            raise ValueError("Provider queue_capacity cannot be negative")
        if self.selection_value is not None and not self.selection_value.strip():
            raise ValueError("Provider selection_value cannot be empty")
        if self.catalog_order < 0:
            raise ValueError("Provider catalog_order cannot be negative")
        keys = [field.key for field in self.config_schema]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Provider {self.provider_id!r} has duplicate config keys")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "stage": self.stage,
            "api_version": self.api_version,
            "implementation_version": self.implementation_version,
            "capabilities": self.capabilities.to_dict(),
            "resource_classes": sorted(self.resource_classes),
            "max_concurrency": self.max_concurrency,
            "queue_capacity": self.queue_capacity,
            "config_schema": [field.to_dict() for field in self.config_schema],
            "legacy_adapter": self.legacy_adapter,
            "selection_value": self.selection_value or self.provider_id,
            "description": self.description,
            "catalog_order": self.catalog_order,
            "model_catalog": [model.to_dict() for model in self.model_catalog],
        }


@dataclass(frozen=True)
class ProviderRequirements:
    stage: ProviderStage
    languages: frozenset[str] = field(default_factory=frozenset)
    devices: frozenset[str] = field(default_factory=frozenset)
    execution_modes: frozenset[str] = field(default_factory=frozenset)
    features: frozenset[str] = field(default_factory=frozenset)
    resource_classes: frozenset[ResourceClass] = field(default_factory=frozenset)
    requires_batch: bool = False

    def __post_init__(self) -> None:
        if self.stage not in VALID_STAGES:
            raise ValueError(f"Unsupported provider stage: {self.stage!r}")
        for name in ("languages", "devices", "execution_modes", "features"):
            object.__setattr__(self, name, frozenset(str(value) for value in getattr(self, name)))
        resources = frozenset(self.resource_classes)
        if not resources.issubset(VALID_RESOURCES):
            raise ValueError(f"Invalid required resource classes: {sorted(resources)!r}")
        object.__setattr__(self, "resource_classes", resources)

    def matches(self, manifest: ProviderManifest) -> bool:
        capabilities = manifest.capabilities
        return (
            manifest.stage == self.stage
            and self.languages.issubset(capabilities.languages)
            and self.devices.issubset(capabilities.devices)
            and self.execution_modes.issubset(capabilities.execution_modes)
            and self.features.issubset(capabilities.features)
            and self.resource_classes.issubset(manifest.resource_classes)
            and (not self.requires_batch or capabilities.supports_batch)
        )
