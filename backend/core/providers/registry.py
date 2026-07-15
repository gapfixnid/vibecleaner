"""Thread-safe provider registration and capability lookup."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Protocol

from .manifest import ProviderManifest, ProviderRequirements, ProviderStage


class ProviderAdapter(Protocol):
    provider_id: str

    def prepare(self, runtime: Any = None) -> None: ...

    def shutdown(self) -> None: ...


@dataclass(frozen=True)
class ProviderRegistration:
    manifest: ProviderManifest
    adapter: ProviderAdapter


class ProviderRegistry:
    CATALOG_SCHEMA_VERSION = 1

    def __init__(self) -> None:
        self._registrations: dict[str, ProviderRegistration] = {}
        self._lock = RLock()

    def register(self, manifest: ProviderManifest, adapter: ProviderAdapter) -> None:
        if adapter is None:
            raise ValueError(f"Provider {manifest.provider_id!r} requires an adapter")
        if getattr(adapter, "provider_id", None) != manifest.provider_id:
            raise ValueError(f"Provider adapter ID does not match manifest: {manifest.provider_id}")
        if not callable(getattr(adapter, "prepare", None)) or not callable(getattr(adapter, "shutdown", None)):
            raise TypeError(f"Provider {manifest.provider_id!r} adapter lacks lifecycle methods")
        with self._lock:
            if manifest.provider_id in self._registrations:
                raise ValueError(f"Provider already registered: {manifest.provider_id}")
            self._registrations[manifest.provider_id] = ProviderRegistration(manifest, adapter)

    def get(self, provider_id: str) -> ProviderRegistration:
        with self._lock:
            try:
                return self._registrations[provider_id]
            except KeyError as exc:
                raise KeyError(f"Provider not registered: {provider_id}") from exc

    def list(self, stage: ProviderStage | None = None) -> tuple[ProviderRegistration, ...]:
        with self._lock:
            registrations = tuple(self._registrations.values())
        if stage is not None:
            registrations = tuple(item for item in registrations if item.manifest.stage == stage)
        return tuple(sorted(registrations, key=lambda item: item.manifest.provider_id))

    def resolve(self, requirements: ProviderRequirements) -> tuple[ProviderRegistration, ...]:
        return tuple(
            registration
            for registration in self.list(requirements.stage)
            if requirements.matches(registration.manifest)
        )

    def catalog(self) -> dict[str, Any]:
        return {
            "schema_version": self.CATALOG_SCHEMA_VERSION,
            "providers": [registration.manifest.to_dict() for registration in self.list()],
        }
