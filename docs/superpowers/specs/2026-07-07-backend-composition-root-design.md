# Backend Composition Root Refactor Design

## Goal

Refactor the backend as a Big Bang structural change, not a folder-only rename.
The finished backend should have explicit dependency direction, a single
composition root, ports between the pipeline and concrete engines, and first
class pipeline support for strategies, validation, and provenance.

The frontend API contract should remain stable unless a route is already unused
or explicitly replaced by an equivalent response shape.

## Target Layout

```text
backend/
  main.py

  api/
    dependencies.py
    routes/
      settings.py
      project.py
      pages.py
      jobs.py
    schemas/
      settings.py
      project.py
      pages.py
      jobs.py
      pipeline.py

  core/
    container.py
    config.py
    errors.py
    models/
      page.py
      bubble.py
      geometry.py
      image.py
      text.py
      jobs.py
    ports/
      detection.py
      ocr.py
      translation.py
      inpainting.py
      rendering.py
      project.py
      assets.py
      cache.py
      jobs.py
    state/
      project_state.py
      repository.py

  pipeline/
    context.py
    plan.py
    planner.py
    runner.py
    registry.py
    provenance.py
    stages/
      detection.py
      ocr.py
      translation.py
      inpainting.py
      layout.py
      rendering.py
      export.py
    strategies/
      quality_profile.py
      engine_selection.py
      model_selection.py
    validation/
      inputs.py
      geometry.py
      results.py

  engines/
    detection/
      adapter.py
      rtdetr.py
      yolo.py
      heuristic.py
    ocr/
      adapter.py
      manga_ocr.py
      paddle_ocr.py
      pororo.py
    translation/
      adapter.py
      cache.py
      llm.py
    inpainting/
      adapter.py
      hybrid.py
      lama.py
      opencv.py
    rendering/
      adapter.py
      layout_planner.py
      text_renderer.py

  infrastructure/
    image/
      loading.py
      encoding.py
      transforms.py
    fonts/
      resolver.py
    cache/
      image_cache.py
      translation_cache.py
    storage/
      export_store.py
      project_store.py
    downloads/
      model_downloader.py
      model_registry.py
    assets/
      paths.py
```

## Dependency Rules

The operational dependency contract lives in
`docs/backend-dependency-contract.md`. Keep that document and this design in
sync whenever the runtime wiring or layer rules change.

Allowed dependency direction:

```text
api -> pipeline, core
pipeline -> core
engines -> core, infrastructure
infrastructure -> core
main/container -> api, pipeline, engines, infrastructure, core
```

Forbidden dependency direction:

```text
core -> api/pipeline/engines/infrastructure
pipeline -> api
pipeline -> concrete engines
engines -> api
engines -> pipeline runner/stages
api routes -> concrete engines or infrastructure internals
```

The only module that may know every concrete implementation is
`backend/core/container.py`.

Current runtime rule: the desktop app is launched through `npm run dev`
(`tauri dev`). Tauri starts Vite and launches `backend/main.py` from the
repository-root `venv/`. Running `npm --prefix frontend run dev` directly is a
browser-only/static-UI mode and does not provide the Tauri command bridge or the
backend process.

## Composition Root

`backend/main.py` should create the FastAPI app and attach a container. It
should not instantiate individual services or engines directly.

```python
def create_app() -> FastAPI:
    container = build_container()
    app = FastAPI(...)
    app.state.container = container
    include_routes(app)
    return app
```

`backend/core/container.py` creates and wires runtime dependencies:

```python
@dataclass
class AppContainer:
    config: AppConfig
    project_repository: ProjectRepository
    job_manager: JobManagerPort
    detector: TextDetector
    ocr: OcrEngine
    translator: Translator
    inpainter: Inpainter
    renderer: Renderer
    pipeline_runner: PipelineRunner
```

Global singleton modules such as `service_registry.py`, module-level
`state = ProjectState()`, and module-level `config = AppConfig()` should be
removed or replaced by container-owned instances.

## API Layer

`backend/api/routes/*` handles HTTP concerns only:

- Parse request data.
- Validate HTTP-level request shape.
- Call container-owned use cases, repositories, job manager, or pipeline runner.
- Return API schema objects.

Routes should get dependencies through `backend/api/dependencies.py`.

```python
def get_container(request: Request) -> AppContainer:
    return request.app.state.container
```

Routes must not directly import engine implementations, storage details, global
config instances, or global project state.

## Core Ports

The pipeline depends on ports instead of concrete engines.

```python
class TextDetector(Protocol):
    def detect(self, image: ImageData, options: DetectionOptions) -> DetectionResult: ...

class OcrEngine(Protocol):
    def recognize(
        self,
        image: ImageData,
        regions: list[TextRegion],
        options: OcrOptions,
    ) -> OcrResult: ...

class Translator(Protocol):
    def translate_batch(
        self,
        items: list[TranslationInput],
        options: TranslationOptions,
    ) -> TranslationResult: ...

class Inpainter(Protocol):
    def inpaint(
        self,
        image: ImageData,
        regions: list[InpaintRegion],
        options: InpaintOptions,
    ) -> InpaintResult: ...

class Renderer(Protocol):
    def render(
        self,
        image: ImageData,
        bubbles: list[Bubble],
        options: RenderOptions,
    ) -> RenderResult: ...

class ProjectRepository(Protocol):
    def list_pages(self) -> list[MangaPage]: ...
    def get_page(self, page_id: str) -> MangaPage: ...
    def save_page(self, page: MangaPage) -> None: ...

class AssetStore(Protocol):
    def resolve_font(self, font_name: str | None) -> FontAsset: ...
    def resolve_model(self, model_id: str) -> ModelAsset: ...
```

Options DTOs live in `core` so engines do not read global settings directly.
Concrete engines receive explicit options from the pipeline strategy layer.

## Pipeline

The page translation route should execute the canonical stage-based runner.

```text
PipelinePlanner
  settings + requested action -> PipelinePlan

PipelineRunner
  PipelineContext + PipelinePlan -> PipelineResult

StageRegistry
  stage name -> Stage implementation

Stage
  run(context) -> StageResult
```

Primary page translation flow:

```text
validate_input
load_page_image
detect_text_regions
run_ocr
translate_text
inpaint_source_text
plan_layout
render_translated_text
save_page_result
```

`PipelineContext` stores all data for a single run:

```python
@dataclass
class PipelineContext:
    page_id: str
    page: MangaPage
    image: ImageData
    settings: AppConfigSnapshot
    artifacts: dict[str, Any]
    provenance: ProvenanceTrace
```

Stages communicate through named artifacts. For example, `DetectionStage`
writes `detection_result`; `OcrStage` reads `detection_result` and writes
`ocr_result`.

## Strategies

Strategies make selection decisions outside concrete engine implementations:

- `QualityProfileStrategy`: speed, balanced, quality.
- `EngineSelectionStrategy`: detection, OCR, inpainting, rendering engine names.
- `ModelSelectionStrategy`: model IDs and backend-specific model options.

Engine implementations should not read `config.detect_model`,
`config.ocr_engine`, or similar global values. The strategy layer converts a
settings snapshot into explicit options passed through core ports.

## Validation

Pipeline validation should produce structured issues instead of raising HTTP
exceptions directly.

```python
@dataclass
class ValidationIssue:
    code: str
    severity: Literal["warning", "error"]
    message: str
    stage: str | None = None
```

Validation responsibilities:

- Input validation: page exists, image can be loaded, required settings are
  present, numeric settings are in range.
- Geometry validation: bounding boxes are non-empty, within image bounds, and
  can be mapped to bubbles or text regions.
- Result validation: detection, OCR, translation, inpainting, and rendering
  results are structurally valid before downstream stages consume them.

Warnings allow the pipeline to continue. Errors stop the runner and return a
structured pipeline failure.

## Provenance

Every stage should record enough information to explain and debug the result.

```python
@dataclass
class StageProvenance:
    stage: str
    engine: str | None
    options: dict[str, Any]
    started_at: datetime
    duration_ms: int
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    warnings: list[str]
    errors: list[str]

@dataclass
class ProvenanceTrace:
    run_id: str
    page_id: str
    stages: list[StageProvenance]
```

Provenance is a runtime artifact first. It can later be surfaced through API or
saved in project metadata, but the initial refactor only needs to capture it in
pipeline results.

## Engine Layer

`engines/*` owns concrete model and rendering behavior. Existing code in
`backend/modules/detection`, `backend/modules/ocr`, `backend/modules/inpainting`,
and `backend/modules/rendering` should be moved or wrapped here.

Each engine group should expose an adapter that satisfies the corresponding
core port. Adapters convert between existing NumPy/TextBlock structures and new
core DTOs while keeping the pipeline independent from concrete engine internals.

## Infrastructure Layer

`infrastructure/*` owns external resource access:

- Image loading, encoding, and transforms.
- Font resolution.
- Translation and image caches.
- Project and export storage.
- Model download, model registry, and model path resolution.
- App asset paths.

Infrastructure modules may depend on core DTOs but must not depend on API
routes or pipeline stages.

## Existing Code Mapping

```text
backend/routes/*                  -> backend/api/routes/*
backend/app/models.py             -> backend/core/models/*
backend/domain/project_state.py   -> backend/core/state/project_state.py
backend/modules/config.py         -> backend/core/config.py

backend page translation workflow
  -> backend/pipeline/page_translation.py
  -> backend/pipeline/page_translation_stages.py
  -> backend/pipeline/runner.py
  -> backend/pipeline/stages/*
  -> backend/pipeline/context.py

backend/services/layout_planner_service.py
  -> backend/engines/rendering/layout_planner.py
  -> backend/pipeline/stages/layout.py

backend/services/detection_service.py
backend/modules/detection/*
  -> backend/engines/detection/*

backend/services/inpainting_service.py
backend/modules/inpainting*
  -> backend/engines/inpainting/*

backend/services/render_service.py
backend/modules/rendering*
  -> backend/engines/rendering/*

backend/modules/utils/download*
  -> backend/infrastructure/downloads/*

backend/modules/utils/image_utils.py
backend/imkit/*
  -> backend/infrastructure/image/*
```

## Testing Strategy

The most important tests are pipeline tests with fake ports. They should verify
stage ordering, artifact handoff, validation failures, and provenance capture
without loading real ML models.

Recommended test layout:

```text
tests/core/
  config/state/model tests

tests/pipeline/
  runner stage ordering
  validation failure
  provenance capture
  fake engine integration

tests/engines/
  adapter option mapping
  bbox/result conversion

tests/api/
  route dependency smoke tests
  translate job submit tests
```

## Completion Criteria

The refactor is complete when:

1. API routes do not import concrete engines, service registry singletons,
   global project state, or global config.
2. Pipeline modules depend on `core.ports` and `core.models`, not concrete
   engine implementations.
3. Detection, OCR, translation, inpainting, and rendering engines receive
   explicit option DTOs instead of reading global settings directly.
4. `service_registry.py` is removed.
5. The page translation route uses the canonical pipeline runner.
6. The project state and config are container-owned instances.
7. `translate-all`, batch translation, inpainting, export, and project/page
   management keep the existing frontend API contract.
8. `provenance`, `strategies`, and `validation` are used by the runner, not
   left as empty directories.
9. Pipeline tests run with fake engines and do not require local model files.
10. Existing relevant backend tests pass or are updated to the new structure.
