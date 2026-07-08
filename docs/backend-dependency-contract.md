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

Legacy modules are not part of the final architecture. If a legacy dependency
still exists, treat it as cleanup debt and remove or absorb it behind a
port-native engine/infrastructure implementation. API routes and pipeline stages
must not reach into legacy modules directly for runtime state, settings, or
concrete engine construction.

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
rg "^service = .*Service\(|^[a-z_]+_service = [A-Z][A-Za-z]+Service\(" backend/services backend/pipeline
rg "from services|import services" backend/pipeline
rg "from modules|import modules" backend/pipeline
rg "modules.logging_config" backend download_models.py tests scripts
```

Expected result: no application imports or singleton definitions that violate
this contract. Test-only compatibility imports should be rare and explicit.
