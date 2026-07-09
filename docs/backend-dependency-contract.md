# Backend Dependency Contract

This document is the working dependency contract for the Big Bang composition
root refactor. Keep it aligned with `README.md` and the design plan under
`docs/superpowers/`.

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

## OCR Concurrency And Cache

Detection and OCR model inference must use separate locks. Cache lookup and
LRU mutation must hold only the cache lock, so a cache hit or manual single
block lookup is never blocked by a different page's OCR inference.

Persistent OCR cache writes use SQLite and are deferred behind a short
write-behind interval. Each flush writes only changed keys in one transaction;
the FastAPI lifespan and process exit handler flush pending changes before
shutdown. The old `ocr_cache.json` is read only for one-time migration.

## Dependency Sets

Use the dependency files for distinct purposes:

| File or command | Purpose |
| --- | --- |
| `npm install` | Installs the root Tauri CLI dependency used by `npm run dev` and `npm run build`. |
| `npm --prefix frontend install` | Installs React, Vite, TypeScript, and Tauri frontend API dependencies. |
| `requirements-runtime.txt` | Default Python backend runtime for local desktop dev and sidecar packaging. Excludes optional Torch packages. |
| `requirements-torch.txt` | Optional Torch-backed model paths for development or advanced local features. |
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
