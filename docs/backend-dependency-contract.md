# Backend Dependency Contract

This document is the dependency contract established by the composition-root
refactor. Keep it aligned with `README.md` and the current architecture
document under `docs/architecture.md`.

Pipeline v2 is the current page-translation runtime and does not require a
second full-product rewrite. Current stage, provider, checkpoint, and rendering
contracts are summarized in `docs/architecture.md`. Persisted contracts follow
`docs/schema-versioning-policy.md`.

## Runtime Entry Points

The desktop app is the primary runtime:

```text
npm run dev
  -> tauri dev
  -> desktop/src-tauri/tauri.conf.json beforeDevCommand
  -> npm --prefix frontend run dev
  -> Rust/Tauri starts backend/main.py from .\venv\Scripts\python.exe
  -> FastAPI routes use app.state.container
```

The React frontend currently calls backend APIs through Tauri commands. Running
Vite directly in a browser is useful for static UI work only; it does not start
the backend and it does not provide the Tauri command bridge.

## Desktop Local-IPC Contract

`BackendManager` is the single owner of the Python child process, session
token, shared HTTP client, lifecycle phase, and monotonically increasing
generation. Each launch uses a random loopback port and a random 32-byte
Base64URL session token. The Python entry point removes the token from its
environment, keeps only decoded bytes, and requires it in
`X-VibeCleaner-Token` on every endpoint except `/health`.

Readiness is an identity check, not merely a successful TCP connection. Tauri
sends a random 32-byte challenge to `/health` and accepts the process only when
the response has protocol version `1` and a valid HMAC-SHA256 proof for the
canonical message `vibecleaner-health-v1:<challenge>`. The shared client does
not use system proxies or redirects and validates its generation after every
response.

Every Tauri API command captures one `BackendSession` at command entry. That
session pins both the shared client and its generation for all reads,
mutations, and job-poll requests performed by the command. Requests validate
the session before sending and after receiving a response; composite commands
also validate it before returning assembled data. A command must never acquire
a second session midway through its work or combine values from two backend
generations.

The child watcher reports `BACKEND_EXITED` only when all of these remain true:

- the watched generation is current;
- the watched PID is still the manager's child; and
- the current phase is `starting` or `running`.

Shutdown and restart first move to `stopping` and take the child from the
manager, so an intentional exit cannot be mistaken for a crash. A restart
increments the generation before entering `restarting`; therefore
`running(g=1) -> restarting(g=1)` is invalid while
`running(g=1) -> restarting(g=2)` is accepted.

Browser code never receives the backend port or token. Images use the
`vibecleaner-image` custom protocol, whose Rust handler accepts only `GET
/api/pages/{page_id}/image`, validates its path and query allowlists, and
forwards only response headers needed to render and cache an image. Other API
traffic stays behind Tauri commands.

Persisted project page IDs are normalized to unique
`[A-Za-z0-9_-]{1,128}` values before pages enter runtime state. Unsafe or
duplicate values are replaced with UUID hex IDs and retained only in the
`vibecleaner_original_page_id` extension field. Every Tauri page/job route
uses the shared path-segment encoder and rejects raw separators, fragments,
queries, control characters, and dot segments. Batch export uses fixed ordinal
filenames and verifies the canonical destination remains inside the selected
output directory; persisted IDs are never used as filesystem names.

## Typesetting Font-Size Contract

Persisted `font_size` remains backward compatible: `0` selects automatic
fitting and a positive integer selects a fixed size. Bubble responses expose
the normalized contract as `font_mode` (`auto` or `fixed`),
`requested_font_size` (only for fixed mode), and `computed_font_size`.

Automatic mode chooses the font size, wrapping, and line positions together.
Fixed mode preserves the requested pixel size and recomputes wrapping and line
positions at that size. If the text cannot fit, it reports layout overflow; it
must not silently shrink. Canvas preview and export both use
`computed_font_size` from the layout, so glyph size and line geometry always
come from the same calculation.

Adaptive Typesetting v2 converts bubble masks to safe text regions with a
distance transform. Planned padding and margin plus the expected text stroke
define the boundary clearance; line slots are intersections of one contiguous
horizontal segment across every glyph row, so a line cannot bridge a concave
or disconnected gap. If the planned padding is too restrictive, the engine
may retry a documented reduced-padding candidate, but it never bypasses the
stroke-safe boundary.

Rectangle and mask layouts share the Unicode boundary tokenizer. Explicit
newlines are mandatory, while Korean eojeol, URLs, number/unit pairs, and
bracket groups remain intact until the grapheme fallback is required. Feasible
candidates are compared lexicographically by invalid breaks, preferred line
count, font size, balance, area use, and vertical placement. Automatic layouts
also test line-height ratios `1.12`, `1.06`, `1.00`, and `1.18`, and use a
page-resolution readability floor clamped to 11–24 px. Identical inputs must
produce identical layout output.

When a newer generation reaches `running`, React atomically stops job polling,
clears pages, bubbles, selections, image versions, dirty state, loading state,
and the active project path before reloading settings and pages. If the prior
generation held in-memory work, the user is warned that unsaved work was lost.
Polling and task epochs are advanced at the same boundary, so completions and
`finally` handlers from the previous backend cannot clear a newer job or busy
state. The running generation is recorded as hydrated only after both settings
and pages load successfully and the generation is still current. Settings and
pages are fetched first and committed together, so a generation change during
hydration cannot leave either half of stale state visible.

`backend/main.py` owns FastAPI app creation. `backend/core/container.py` is the
composition root that wires concrete runtime dependencies.

## Layer Ownership

| Layer | Owns | May Depend On | Must Not Depend On |
| --- | --- | --- | --- |
| `backend/api` | HTTP routes, request parsing, response schemas | `backend/core`, container-owned use cases, FastAPI dependencies | concrete engines, infrastructure internals, global state/config singletons |
| `backend/core` except `container.py` | models, ports, config snapshots, errors, state contracts | standard library and stable third-party types | API, pipeline stages, concrete engines, infrastructure helpers |
| `backend/pipeline` | plans, runner, stages, strategies, validation, provenance | `backend/core` contracts and sibling pipeline modules | API routes, concrete engines, service registry, module-level config/state |
| `backend/engines` | concrete detection, OCR, translation, inpainting, rendering adapters | `backend/core`, infrastructure helpers, external model libraries | API routes, pipeline runner/stages, FastAPI dependencies |
| `backend/infrastructure` | image, font, cache, storage, download, asset access | `backend/core` DTOs and external libraries | API routes, pipeline runner/stages |
| `backend/core/container.py` | runtime assembly | all backend layers needed for wiring | business logic that belongs in routes, stages, or adapters |

The container is the only backend module that may know the full concrete object
graph. New runtime dependencies should be added there first, then passed inward
through explicit constructor arguments or port methods.

## Forbidden Application Coupling

Application code must not introduce these dependencies:

```powershell
from services.service_registry import ...
from modules.config import config
from engines...              # inside backend/api or backend/pipeline
import engines               # inside backend/api or backend/pipeline
state = ProjectState(...)
config = AppConfig(...)
```

The legacy `backend/modules` package has been fully removed: engine
implementations live in `backend/engines/*`, shared engine domain types in
`backend/engines/common`, and resource helpers in `backend/infrastructure/*`.
`AppConfig` lives in `backend/core/config.py` and receives its settings path
by injection from the container. New code must not reintroduce a
`backend/modules` package or module-level runtime state/config singletons.

The legacy `backend/app` and `backend/routes` packages are also removed:
runtime domain models (`TextBubble`, `MangaPage`) live in
`backend/core/models/page.py`, version constants in `backend/core/version.py`,
the offscreen Qt bootstrap in `backend/infrastructure/runtime/qt.py`, and
bundled fonts under `backend/infrastructure/assets/fonts/`.

`backend/core` and `backend/pipeline` are Qt-free. Bubble geometry uses
`core.models.geometry.Rect`; only rendering-engine code converts `Rect` to
`QRectF` at its own boundary.

The `backend/services` layer has been fully absorbed:

| Former module | New home |
| --- | --- |
| `image_encoding_service`, `page_image_loader` | `infrastructure/image/{encoding,loading}.py` |
| `cache_service` | `infrastructure/cache/tasks.py` |
| `job_service` | `infrastructure/jobs.py` (`JobManager`, container-owned instance) |
| `model_requirements` | `infrastructure/downloads/requirements.py` |
| `review_state_service` | `core/state/review.py` |
| `export_service` | `engines/rendering/export.py` |
| `page_analysis_service`, `bubble_analysis_service` | `pipeline/analysis/{page,bubbles}.py` |
| route use-case helpers | `backend/api/use_cases/*` |

API use cases receive `job_manager` and engine services as explicit arguments
from routes (sourced from the container); there is no module-level
`job_manager` singleton. The cache warm-up executor is likewise a
container-owned `CacheTaskQueue` instance, not a module-level executor.

HTTP concerns stay in the API layer: `backend/core`, `backend/pipeline`,
`backend/engines`, and `backend/infrastructure` must not import `fastapi`.
Lower layers raise `core.errors` domain errors (`PageNotFoundError`,
`PageImageLoadError`); `backend/main.py` maps them to HTTP responses with
exception handlers.

API code may import stateless helper facades from `infrastructure`
(e.g. `infrastructure.image.encoding`/`loading`) directly — "infrastructure
internals" means private implementation modules and stateful resources, which
must be container-owned.

## Settings And Engine Options

Settings flow through explicit values:

```text
AppConfig owned by AppContainer
  -> AppConfigSnapshot
  -> pipeline strategies
  -> DetectionOptions / OcrOptions / TranslationOptions / InpaintOptions / RenderOptions
  -> engine adapters
```

Concrete engines should receive option DTOs or constructor dependencies. They
should not read module-level settings directly during request execution.

## Pipeline Contract

The page translation path runs through the pipeline runner:

```text
PipelinePlanner -> PipelinePlan
PipelineRunner -> StageRegistry -> stages
stages -> core ports
runner -> validation issues and provenance trace
```

`provenance`, `strategies`, and `validation` are not placeholders. The runner
must record stage execution, strategies must translate settings into options,
and validation must return structured issues that can stop unsafe downstream
work.

Pipeline v2 stages communicate through explicit, versioned DTOs and stable core
ports. A stage must not import a concrete provider or model class. Provider
selection is capability-based through a registry assembled at the composition
root; adding a provider must not require provider-specific pipeline, API, or UI
branches.

## OCR Concurrency And Cache

Detection and OCR model inference must use separate locks. Cache lookup and
LRU mutation must hold only the cache lock, so a cache hit or manual single
block lookup is never blocked by a different page's OCR inference.

Persistent OCR cache writes use SQLite and are deferred behind a short
write-behind interval. Each flush writes only changed keys in one transaction;
the FastAPI lifespan and process exit handler flush pending changes before
shutdown. The old `ocr_cache.json` is read only for one-time migration.

## Batch Job Results

Batch page translation must report page-scoped outcomes. `successful_pages`
counts only pages whose translation completed; it must never mean loop
iterations. Results include `successful_page_indices` and
`failed_pages[{page_id, page_idx, error}]`.

Job status is `succeeded` when every page succeeds,
`succeeded_with_errors` for a mixed outcome, and `failed` when no page
succeeds. Clients must treat `succeeded_with_errors` as a completed operation
and surface its failed page details.

## Dependency Sets

Use the dependency files for distinct purposes:

| File or command | Purpose |
| --- | --- |
| `npm install` | Installs the root Tauri CLI dependency used by `npm run dev` and `npm run build`. |
| `npm --prefix frontend install` | Installs React, Vite, TypeScript, and Tauri frontend API dependencies. |
| `requirements-runtime.txt` | ONNX Runtime backend for local desktop development and sidecar packaging. |
| `requirements-build.txt` | PyInstaller-only dependencies for building the backend sidecar. |
| `requirements.txt` | Full development environment. Do not use this for lean release sidecar packaging. |

The normal development backend environment is the repository-root `venv/`.
Tauri's dev launcher expects `.\venv\Scripts\python.exe` on Windows.

## Boundary Checks

Run these before claiming dependency boundaries are clean:

```powershell
rg "from engines|import engines" backend/pipeline backend/api
rg "service_registry|state = ProjectState\(|config: AppConfig = AppConfig\(" backend
rg "domain.project_state|legacy_state|from modules.config import config" backend tests
rg "from services|import services" backend tests download_models.py scripts
rg "from modules|import modules" backend tests download_models.py scripts
rg "modules.logging_config" backend download_models.py tests scripts
rg "^from app\.|^import app\." backend tests download_models.py scripts
rg "PySide6" backend/core backend/pipeline
rg "^from api|^import api" backend/pipeline backend/core backend/engines backend/infrastructure
rg "fastapi" backend/core backend/pipeline backend/engines backend/infrastructure
```

Expected result: no application imports or singleton definitions that violate
this contract. Test-only compatibility imports should be rare and explicit.
