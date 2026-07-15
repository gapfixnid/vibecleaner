# ADR 0001: Evolve the Pipeline Core Without a Full Rewrite

- Status: Accepted
- Date: 2026-07-13
- Scope: v0.2 pipeline architecture and migration

## Context

VibeCleaner already has a working Tauri shell, React workspace, editing model,
engine implementations, project persistence, and export workflow. The next
pipeline needs independently scheduled detection and OCR, resource-aware DAG
execution, provider limits, checkpoints, quality routing, and capability-based
engine selection. Rebuilding the product around those changes would expand the
scope, put existing project data at risk, and delay measurable improvements.

The current dependency contract and composition root are useful foundations.
The migration must strengthen those boundaries instead of creating a second
application alongside them.

## Decision

### This is a core replacement, not a product rewrite

VibeCleaner v2 will preserve roughly 70-80% of the product's responsibility
areas and replace the 20-30% that determines pipeline performance, quality,
and extensibility. These percentages describe responsibility boundaries, not
lines of code or a delivery target.

A change to a preserved area must be limited to a compatibility adapter, typed
contract, manifest-driven presentation, feature-flag connection, or another
measurable requirement of the core migration. A broader redesign requires a
separate ADR with evidence that the preserved implementation blocks a v2 exit
criterion.

| Preserve | Replace or add |
| --- | --- |
| Tauri desktop shell and sidecar lifecycle | Pipeline Scheduler/Executor v2 |
| React workspace, Canvas, and Inspector | Truly independent detection and OCR stages |
| Project, page, bubble, and manual-edit behavior | Typed stage DTOs and versioned artifacts |
| Existing API behavior and Tauri commands | Resource-aware dependency DAG execution |
| Existing detection, OCR, translation, inpainting, and rendering engines | Adaptive quality routing and confidence validation |
| Existing core ports and engine adapters where compatible | Provider manifest, capability catalog, and resolver |
| Model download and packaging flow | Artifact cache, checkpoints, and partial retry |
| Save, load, export, and user correction preservation | Project terminology, character, and context memory |
| Existing provider integrations | Typesetting quality gates and automatic replanning |
| Existing boundary tests | v1/v2 shadow comparison and rollout controls |

Preservation does not freeze defects. It prevents unrelated redesign while the
pipeline core is being replaced.

### Dependency and extension rules

The rules in `docs/backend-dependency-contract.md` remain binding. Pipeline v2
adds these constraints:

- Domain contracts and decisions must not depend on FastAPI, React, Tauri, Qt,
  or a concrete model library.
- Every engine is accessed through a stable, stage-specific port. A pipeline
  stage must not import a concrete engine or model class.
- Stage inputs and outputs are explicit DTOs. An untyped artifact dictionary
  may exist inside an executor as storage, but it is not a stage contract.
- Provider selection is based on declared capabilities and runtime constraints,
  not provider-name conditionals in stages.
- A provider is added by implementing an adapter, registering a manifest,
  declaring capabilities, and supplying benchmark evidence. Adding a provider
  must not require edits to the pipeline, API routing, or provider-specific UI.
- A provider manifest owns its stable ID, API and implementation versions,
  stage, capabilities, resource needs, concurrency defaults, configuration
  schema, artifact compatibility, model checksums, and license metadata.
- Advanced settings are rendered from manifest configuration schemas. The UI
  may own generic controls but must not hard-code fields for individual models.
- The composition root or a registry assembled by it is the only place that
  binds provider implementations to ports.
- Project, settings, artifact, and cache formats follow
  `docs/schema-versioning-policy.md`.
- Import boundaries, manifest validity, DTO compatibility, and migration rules
  are executable CI checks, not review conventions only.

Stage-specific ports follow this lifecycle shape; request/result and capability
types belong to the core contract, while implementation details stay in the
adapter:

```python
class OcrProvider(Protocol):
    provider_id: str
    capabilities: OcrCapabilities

    def prepare(self, runtime: RuntimeContext) -> None: ...
    def recognize(self, request: OcrRequest) -> OcrResult: ...
    def shutdown(self) -> None: ...
```

Other provider stages use the equivalent typed contract. Provider-private
configuration is validated from the manifest before the adapter is prepared.

### Strangler migration

Pipeline v1 remains the production path while v2 is introduced beside its
contracts:

```text
v1 remains available
  -> run v2 in an isolated shadow mode on the same input
  -> compare stage outputs, latency, resource use, and failures
  -> enable v2 for explicit opt-in and internal cohorts
  -> expand rollout only after benchmark and compatibility gates pass
  -> make v2 the default while retaining one-action rollback to v1
  -> observe the defined stabilization window
  -> remove v1 in a separate, explicit decision
```

Shadow execution must not mutate the active project, overwrite user edits, or
publish v2 output as the user's result. Comparison artifacts use a separate
namespace and may be discarded. Feature flags must independently control shadow
execution and user-visible v2 execution.

Migration slices must leave the application runnable. Detection/OCR separation,
DAG execution, resource controls, caching, and quality routing are introduced
behind contracts and flags rather than landed as one replacement patch.

### Default and removal gates

V2 may become the default only when all of these are true:

- Accuracy, correction-rate, latency, throughput, and resource thresholds from
  the versioned benchmark suite pass for two consecutive release candidates.
- Project and public API compatibility fixtures pass without user-data loss,
  including manual bubble edits and partial results.
- Cancellation, restart, retry, checkpoint recovery, cache corruption, provider
  failure, and out-of-memory paths have no unresolved release-blocking defects.
- Shadow comparisons explain material output differences; silent divergence is
  not accepted as success.
- The release has a tested, single-action rollback to v1 that does not require a
  project-format downgrade.

Making v2 the default does not authorize v1 removal. V1 removal requires a
separate ADR after the stabilization window and additionally requires:

- no supported project or API client depends on v1-only behavior;
- v2 has remained the default for at least one stable release;
- rollback and failure metrics stayed within the release thresholds;
- migration and recovery documentation is shipped; and
- v1 fixtures remain available for compatibility tests after runtime code is
  removed.

## Consequences

- Delivery is incremental and produces comparison data before user-visible
  cutover.
- Existing engines can initially be wrapped rather than rewritten.
- Compatibility adapters and temporary dual execution add short-term code and
  operational cost.
- Preserved UI and persistence contracts constrain some v2 implementation
  choices; changing them requires explicit evidence and a new decision.
- Architecture and migration checks become release gates for Phase A onward.
