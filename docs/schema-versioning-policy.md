# Schema Versioning and Compatibility Policy

This policy governs persisted project files, application settings, pipeline
artifacts/checkpoints, and caches. It implements the architecture policy that
the pipeline core can change without breaking user data.

## Version identity

Application release versions and data schema versions are independent:

- `app_version` identifies the VibeCleaner build that wrote data.
- `schema_version` identifies the shape and semantics of one format family.
- `provider_api_version` identifies an adapter contract.
- `provider_version` and `model_version` identify the producing implementation
  and model. They participate in artifact/cache compatibility but never replace
  `schema_version`.

Schema versions are monotonically increasing integers scoped to a format
family. They are not semantic versions. Project, settings, each artifact type,
and each cache namespace advance independently.

Every new serialized envelope must include its format family and
`schema_version`. Writers always emit the current version. Readers declare the
exact versions they support; "best effort" parsing of an unknown future version
is forbidden.

## Current-format baseline

Phase A records existing unversioned or partially versioned formats as legacy
inputs rather than silently redefining them:

| Format | Baseline interpretation | Adoption rule |
| --- | --- | --- |
| Zip project `project.json` with `"version": "2.0"` | project schema 2 | Migrate in memory through schema 3. Bubble review strings become structured `code + detail` records; unknown strings are preserved as separate `LEGACY_REVIEW_NOTE` values. |
| Current project `project.json` with `"version": "3.0"` | project schema 3 | Bubble review problems are structured records. Writers emit schema 3 only after migration and validation. |
| Legacy standalone JSON project | project schema 1 | Import through explicit 1 -> 2 -> 3 migrations; never overwrite the source during import. |
| Settings JSON without a version | settings schema 0 | Run existing value migrations as the 0 -> 1 migration, then persist a version only through an atomic save. |
| Current `ocr_cache.sqlite3` without schema metadata | cache family `ocr-text`, schema 1 | Adopt it after validating the known table shape; create metadata as part of an idempotent migration. |
| Legacy `ocr_cache.json` | cache family `ocr-text`, schema 0 | Migrate 0 -> 1 or discard safely if invalid. |
| Pipeline v2 artifacts and checkpoints | no legacy version | Start each artifact family at schema 1. |

This table is a compatibility decision, not proof that the corresponding
migrations are already implemented.

Project schema 2 review-string migration recognizes only the documented exact
legacy values. Any other string—including provider or connection errors that
happen to contain words such as `ocr` or `translation`—becomes its own
`LEGACY_REVIEW_NOTE` with the original text preserved in `detail`.

## Format contracts

### Projects

Projects contain durable user work. A project envelope records at least
`format: "vibecleaner-project"`, `schema_version`, `app_version`, and the
project payload. Durable manual edits, selected pages, partial completion, and
source references belong to the project contract, not to a disposable cache.

- Load validates the envelope and archive members before changing active state.
- Older supported versions migrate sequentially in memory, validate at the
  current version, and only then replace active state.
- Saving uses a temporary file and atomic replacement. An existing project is
  not truncated before the new archive is complete and readable.
- An unsupported future version is rejected with a clear required/current
  version error. It is never opened and then saved as an older version.
- Unknown fields are preserved where round-trip compatibility is promised;
  destructive normalization requires a documented migration.

### Settings

Settings record `format: "vibecleaner-settings"`, `schema_version`, and
`app_version`. Secrets continue to follow their existing storage boundary and
must not be copied into manifests, artifacts, logs, or benchmark fixtures.

- Missing keys receive documented defaults; invalid known keys produce a
  validation warning or error rather than an arbitrary coercion.
- Renamed or removed keys are handled by a sequential migration, not scattered
  provider-name checks in UI and runtime code.
- Unknown future schemas are not written back. The application may start with
  safe defaults only after preserving the unread settings and clearly warning
  the user.

### Pipeline artifacts and checkpoints

Every stored artifact uses an envelope equivalent to:

```text
artifact_type, schema_version, app_version, stage_id, stage_version,
provider_id, provider_version, model_id, model_version,
input_fingerprint, config_fingerprint, context_fingerprint, payload
```

The exact fields may be typed DTOs rather than a literal flat object. An
artifact is reusable only when its schema and all compatibility fingerprints
match the consumer's declared requirements. Stage code consumes typed DTOs and
does not inspect provider-private payloads.

Checkpoints reference immutable artifacts and record DAG completion state.
Resume validates every referenced artifact before scheduling downstream work.
A missing or incompatible artifact invalidates that stage and its dependents,
not unrelated completed stages. User-authored corrections must be promoted to
the project format; they must never exist only in a disposable checkpoint.

### Caches

Each persistent cache has a family/namespace, schema version, producer identity,
and compatibility-key definition. Cache keys include every input that can change
the meaning of a result, including provider/model version, relevant settings,
input content, artifact schema, and project context where applicable.

Caches contain no sole copy of user-authored data. On unknown schema, corrupt
metadata, or incompatible producer semantics, the safe behavior is to quarantine
or delete the affected namespace and recompute it. A cache migration is useful
only when cheaper and equally safe; otherwise invalidation is the migration.

## Migration contract

For each format family, migrations form a registered linear chain:

```text
read n -> validate n -> migrate n to n+1 -> validate n+1 -> ... -> current
```

Every migration must be deterministic, idempotent on its declared input,
side-effect free while transforming data, and covered by a golden fixture. It
must document defaults, renamed/removed fields, possible information loss, and
rollback behavior. Validation runs before and after each step. Filesystem writes
occur only after the whole chain succeeds and use backup/atomic-replace behavior
appropriate to the format.

Skipping versions, using the application version as a schema version, or
mutating a project while it is only partially migrated is forbidden. Failed
project/settings migrations preserve the original bytes and return an actionable
error. Failed artifact migrations trigger stage recomputation; failed cache
migrations trigger namespace invalidation.

## Compatibility and API policy

- Changes within a schema version are backward-compatible additions only and
  must define defaults for old readers/fixtures.
- Removing, renaming, changing meaning/type, or tightening a formerly valid
  constraint requires a schema increment and migration.
- Public API changes remain additive during the v2 rollout. A breaking API
  shape requires an explicit API version and compatibility adapter; switching
  pipeline implementations is not itself permission to change the API.
- Internal implementation or model changes must not force a project schema
  change unless durable project semantics change. They normally invalidate an
  artifact/cache compatibility key instead.

## Deprecation and retention

A persisted field, provider manifest field, or supported schema cannot be
removed until it has been marked deprecated in release notes and runtime
diagnostics for at least two minor releases. The deprecation notice names the
replacement, migration behavior, last supported reader, and planned removal
version. Security or data-corruption fixes may shorten this window, but require
a dedicated architecture decision and recovery instructions.

Deprecated cache schemas may be invalidated sooner because caches are
rebuildable, but the release notes must state the performance/storage impact.
Compatibility fixtures are retained after runtime support ends so accidental
reuse of an old version is detected.

## Required verification

CI must cover:

- golden load and round-trip fixtures for every supported project version;
- preservation of manual edits, partial state, page order, and selections;
- one-step and full-chain settings migrations;
- deterministic artifact serialization and compatibility-key changes;
- checkpoint resume with one missing, corrupt, or stale dependency;
- cache adoption, invalidation, and legacy JSON migration;
- explicit rejection of unsupported future schemas; and
- architecture checks that prevent stages and UI from bypassing versioned
  contracts or provider manifests.

