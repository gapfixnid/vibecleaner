# Provider Extension Contract

Phase B introduces a manifest and registry before changing pipeline execution.
The current engines remain active through compatibility registrations; the
registry is metadata and lookup infrastructure, not a second service locator.

## Stable contract

Provider manifests are defined in `backend/core/providers`. They contain only
serializable metadata and core-owned capability terms:

- stable `provider_id`, stage, API version, and implementation version;
- supported languages, devices, local/remote modes, features, and batching;
- CPU/GPU/I/O/network resource classes and a concurrency default;
- generic configuration field declarations; and
- whether the registration is a temporary v1 compatibility adapter.

During the compatibility window, `selection_value` maps a stable manifest ID
to the existing persisted setting value. New project formats should persist the
stable provider ID; the alias exists so the catalog-driven UI can be introduced
without rewriting existing settings first. `model` fields request the generic
live-model picker, while string/secret/enum/boolean/number fields use generic
controls. Labels, placeholders, and help text may be localization keys.
Numeric fields declare optional minimum, maximum, and step constraints; enum
fields may declare localized choice labels. `visible_when_key/value` supports
simple dependent controls without provider-specific JSX. Translation,
detection, OCR, and inpainting settings now use this catalog contract, while
the previous controls remain available only as a catalog-load fallback during
the migration window.

Runtime adapters are stored separately by `ProviderRegistry`. Catalog responses
never contain adapter objects, credentials, secret defaults, or current secret
values. The read-only catalog is available at `GET /api/providers/catalog` and
through the Tauri `get_provider_catalog` command.

## Registration boundary

Concrete engine registration belongs to the composition root. Engine packages
may define their manifests, but pipeline stages and API routes may only depend
on core provider contracts. The API reads the catalog from the container and
does not import engine implementations.

The v1 detection service currently implements combined detection/OCR behavior.
It is registered under separate detection and OCR manifests pointing to the
same compatibility adapter. This is explicit technical debt; Phase C replaces
it with independent typed adapters without changing the manifest IDs silently.

## Adding a provider

1. Implement the stage port/adapter without importing pipeline or API modules.
2. Declare a manifest with the smallest truthful capability set.
3. Register the adapter and manifest at the composition root.
4. Add contract and benchmark evidence for each declared capability.

A provider must not require a provider-name conditional in pipeline stages or
provider-specific JSX. Advanced UI controls consume `config_schema`; generic UI
components may interpret field types but may not contain model-specific fields.

Duplicate IDs, invalid stages/resources, secret defaults, empty enum choices,
and duplicate configuration keys are rejected during registration. Capability
resolution returns all matching registrations in deterministic ID order; model
ranking and benchmark winner selection remain a later resolver concern.
