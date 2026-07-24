# Current architecture

VibeCleaner currently uses the v2 page-translation pipeline as its only page
translation runtime. The application keeps the Tauri desktop shell, React
workspace, project persistence, editing model, export flow, and public API
contracts while the processing pipeline is organized as explicit stages:

```text
detection -> OCR -> translation -> inpainting -> layout -> rendering
```

Stages communicate through validated artifacts and stable core contracts. The
DAG executor owns dependencies, resource classes, retries, cancellation,
provenance, quality decisions, and checkpoint resume. Provider implementations
are selected through the registry and capability manifests rather than being
imported directly by stages.

## Canonical text layers

Non-selected bubble text is rasterized once by the backend Qt renderer into a
cropped transparent PNG at page-native coordinates. Canvas display and export
reuse that same text layer. The selected bubble uses an editing overlay.

Qt application and bundled-font ownership stays on the backend main thread;
Qt shaping and rasterization objects stay on the dedicated render worker.
Layout and paint fingerprints, immutable resource URLs, revision guards, and
fallback states make cache reuse and visual mutations explicit.

If a safe PNG cannot be produced for one bubble, the translated domain state
is preserved and that bubble enters fallback editing mode. A single bubble
failure does not silently replace the canonical renderer or invalidate the
whole page.

## Checkpoints and recovery

Checkpoints store completed stages and serializable stage artifacts. The input
identity includes the page, project generation, visual revisions, settings
digest, and model digest. Live page objects, runtime services, and final render
results are not checkpoint payloads. Resume hydrates only compatible artifacts;
the final commit validates the live page identity before applying changes.

## Extension and compatibility rules

- Domain contracts do not depend on FastAPI, React, Tauri, Qt, or a concrete
  model library.
- Engines are accessed through stage-specific ports and capability manifests.
- Persisted project, settings, artifact, and cache formats follow the schema
  versioning policy.
- New providers require an adapter, manifest, capability declaration, model
  checks, and benchmark evidence.
- Quality, cancellation, retry, checkpoint, and compatibility behavior must be
  covered by executable tests.

This document describes the current implementation. Historical migration
plans and superseded rollout proposals are intentionally not part of the
supported documentation set.
