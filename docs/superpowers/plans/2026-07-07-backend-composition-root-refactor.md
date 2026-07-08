# Backend Composition Root Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the backend into an explicit `api/core/pipeline/engines/infrastructure` architecture with a single composition root and no route-to-engine or pipeline-to-concrete-engine coupling.

**Architecture:** `backend/core/container.py` owns runtime assembly. API routes access dependencies through FastAPI `Depends`; pipeline code depends only on `core.models` and `core.ports`; concrete engines and infrastructure are injected into pipeline stages by the container.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, pytest, NumPy/OpenCV/PIL, existing local model wrappers.

## Global Constraints

- Preserve the existing frontend API contract for settings, project, pages, jobs, translate-all, batch translation, inpainting, export, and bubble actions.
- Do not let `backend/pipeline` import concrete `backend/engines` modules.
- Do not let `backend/api/routes` import concrete engines, `service_registry`, global state, or global config.
- Use container-owned instances instead of module-level `state`, `config`, or `service_registry` singletons.
- `provenance`, `strategies`, and `validation` must be used by the runner.
- Pipeline tests must run with fake engines and without local model files.

---

## File Structure

Create:

- `backend/api/__init__.py`: API package marker.
- `backend/api/dependencies.py`: FastAPI dependency helpers for `AppContainer`.
- `backend/api/routes/*.py`: moved route modules.
- `backend/api/schemas/*.py`: request/response DTOs currently embedded in routes.
- `backend/core/container.py`: composition root and `AppContainer`.
- `backend/core/errors.py`: domain and pipeline exceptions.
- `backend/core/models/*.py`: page, bubble, geometry, image, text, job DTOs.
- `backend/core/ports/*.py`: Protocol contracts and option/result DTOs.
- `backend/core/state/*.py`: `ProjectState` and in-memory repository.
- `backend/pipeline/*.py`: context, plan, planner, runner, registry, provenance.
- `backend/pipeline/stages/*.py`: stage implementations.
- `backend/pipeline/strategies/*.py`: settings-to-options selection.
- `backend/pipeline/validation/*.py`: structured validation.
- `backend/engines/*/adapter.py`: concrete port adapters around existing implementations.
- `backend/infrastructure/*/*.py`: image, font, cache, storage, download helpers.

Modify:

- `backend/main.py`: create container, attach it to app state, include new routers.
- Existing tests under `tests/`: update imports and add pipeline/container tests.
- `pyproject.toml`: update mypy override from `modules.*` to include temporary legacy modules during migration if any remain.

Remove after replacement:

- `backend/services/service_registry.py`
- Module-level page-translation pipeline singletons.
- Module-level singleton access from `backend/domain/project_state.py`
- Module-level singleton access from `backend/modules/config.py`

---

### Task 1: Core Models, Ports, and State

**Files:**
- Create: `backend/core/models/geometry.py`
- Create: `backend/core/models/image.py`
- Create: `backend/core/models/text.py`
- Create: `backend/core/models/page.py`
- Create: `backend/core/models/jobs.py`
- Create: `backend/core/ports/detection.py`
- Create: `backend/core/ports/ocr.py`
- Create: `backend/core/ports/translation.py`
- Create: `backend/core/ports/inpainting.py`
- Create: `backend/core/ports/rendering.py`
- Create: `backend/core/ports/project.py`
- Create: `backend/core/state/project_state.py`
- Create: `backend/core/state/repository.py`
- Test: `tests/test_core_contracts.py`

**Interfaces:**
- Produces: `Box`, `ImageData`, `TextRegion`, `MangaPage`, `Bubble`, `ProjectRepository`, `TextDetector`, `OcrEngine`, `Translator`, `Inpainter`, `Renderer`.
- Consumes: Existing `backend/app/models.py` only as a migration reference.

- [ ] **Step 1: Write failing core contract tests**

```python
from core.models.geometry import Box
from core.models.image import ImageData
from core.state.project_state import ProjectState
from core.state.repository import InMemoryProjectRepository


def test_box_clamps_to_image_bounds():
    box = Box(x1=-10, y1=5, x2=120, y2=90)
    assert box.clamp(width=100, height=80) == Box(x1=0, y1=5, x2=100, y2=80)


def test_box_rejects_empty_geometry():
    box = Box(x1=5, y1=5, x2=5, y2=7)
    assert not box.is_valid()


def test_repository_returns_page_by_id():
    state = ProjectState()
    repo = InMemoryProjectRepository(state)
    page = repo.create_page(name="page-1", image_path="C:/tmp/page.png")
    assert repo.get_page(page.id).id == page.id
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/test_core_contracts.py -v`
Expected: FAIL because the new core modules do not exist.

- [ ] **Step 3: Implement minimal core contracts**

Create dataclass DTOs and Protocols with the names from this task. `Box.clamp`
must return a new `Box`; `Box.is_valid` must require `x2 > x1` and `y2 > y1`.
`InMemoryProjectRepository.create_page` must create a `MangaPage` with a stable
UUID string id and append it to `ProjectState.pages`.

- [ ] **Step 4: Run core tests**

Run: `pytest tests/test_core_contracts.py -v`
Expected: PASS.

---

### Task 2: Pipeline Foundation with Validation and Provenance

**Files:**
- Create: `backend/pipeline/context.py`
- Create: `backend/pipeline/plan.py`
- Create: `backend/pipeline/provenance.py`
- Create: `backend/pipeline/registry.py`
- Create: `backend/pipeline/validation/inputs.py`
- Create: `backend/pipeline/validation/results.py`
- Create: `backend/pipeline/runner.py`
- Test: `tests/test_pipeline_runner_contract.py`

**Interfaces:**
- Consumes: `ProjectRepository`, core port protocols, `MangaPage`, `ImageData`.
- Produces: `PipelineContext`, `PipelinePlan`, `PipelineRunner`, `Stage`, `StageRegistry`, `ProvenanceTrace`, `ValidationIssue`.

- [ ] **Step 1: Write failing runner tests**

```python
from pipeline.plan import PipelinePlan
from pipeline.registry import StageRegistry
from pipeline.runner import PipelineRunner


class RecordingStage:
    name = "record"

    def run(self, context):
        context.artifacts["recorded"] = True
        return context


def test_runner_executes_stage_and_records_provenance(fake_pipeline_context):
    registry = StageRegistry()
    registry.register(RecordingStage())
    runner = PipelineRunner(registry=registry)

    result = runner.run(fake_pipeline_context, PipelinePlan(stages=["record"]))

    assert result.succeeded
    assert result.context.artifacts["recorded"] is True
    assert result.context.provenance.stages[0].stage == "record"
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/test_pipeline_runner_contract.py -v`
Expected: FAIL because pipeline foundation modules do not exist.

- [ ] **Step 3: Implement runner foundation**

Implement:

- `PipelinePlan(stages: list[str])`
- `PipelineContext(page_id, page, image, settings, artifacts, provenance)`
- `Stage` Protocol with `name: str` and `run(context) -> PipelineContext`
- `StageRegistry.register(stage)` and `StageRegistry.get(name)`
- `PipelineRunner.run(context, plan) -> PipelineResult`
- `ProvenanceTrace.start_stage(name)` and `finish_stage(...)`
- `ValidationIssue(code, severity, message, stage=None)`

Runner must stop and return `succeeded=False` if a stage raises a pipeline
validation error.

- [ ] **Step 4: Run runner tests**

Run: `pytest tests/test_pipeline_runner_contract.py -v`
Expected: PASS.

---

### Task 3: Strategy Layer and Option DTOs

**Files:**
- Create: `backend/core/config.py`
- Create: `backend/pipeline/strategies/quality_profile.py`
- Create: `backend/pipeline/strategies/engine_selection.py`
- Create: `backend/pipeline/strategies/model_selection.py`
- Test: `tests/test_pipeline_strategies.py`

**Interfaces:**
- Consumes: `AppConfigSnapshot`.
- Produces: `DetectionOptions`, `OcrOptions`, `TranslationOptions`, `InpaintOptions`, `RenderOptions`.

- [ ] **Step 1: Write failing strategy tests**

```python
from core.config import AppConfigSnapshot
from pipeline.strategies.engine_selection import EngineSelectionStrategy


def test_detection_options_are_resolved_from_snapshot():
    settings = AppConfigSnapshot(
        detect_model="Small (INT8)",
        confidence_threshold=0.42,
        tiling_enabled=False,
        ocr_engine="balanced",
        inpaint_engine="opencv",
    )

    options = EngineSelectionStrategy().detection_options(settings)

    assert options.model_name == "Small (INT8)"
    assert options.confidence_threshold == 0.42
    assert options.tiling_enabled is False
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/test_pipeline_strategies.py -v`
Expected: FAIL because strategy modules do not exist.

- [ ] **Step 3: Implement settings snapshot and option mapping**

Create immutable dataclasses for settings snapshots and engine options. Include
only fields used by existing detection, OCR, translation, inpainting, and
rendering flows. Defaults must match existing `modules.config.AppConfig`.

- [ ] **Step 4: Run strategy tests**

Run: `pytest tests/test_pipeline_strategies.py -v`
Expected: PASS.

---

### Task 4: Concrete Engine Adapters

**Files:**
- Create: `backend/engines/detection/adapter.py`
- Create: `backend/engines/ocr/adapter.py`
- Create: `backend/engines/translation/adapter.py`
- Create: `backend/engines/inpainting/adapter.py`
- Create: `backend/engines/rendering/adapter.py`
- Test: `tests/test_engine_adapters.py`

**Interfaces:**
- Consumes: core option/result DTOs and existing concrete implementation code.
- Produces: classes implementing `TextDetector`, `OcrEngine`, `Translator`, `Inpainter`, `Renderer`.

- [ ] **Step 1: Write failing adapter tests with fakes**

```python
from core.models.geometry import Box
from core.models.image import ImageData
from core.ports.detection import DetectionOptions
from engines.detection.adapter import DetectionEngineAdapter


class FakeLegacyDetector:
    def detect(self, image):
        return [type("LegacyBlock", (), {"xyxy": [1, 2, 11, 12], "text": ""})()]


def test_detection_adapter_converts_legacy_blocks_to_regions():
    adapter = DetectionEngineAdapter(engine=FakeLegacyDetector())
    image = ImageData(array=None, width=100, height=100, mode="RGB")

    result = adapter.detect(image, DetectionOptions())

    assert result.regions[0].box == Box(x1=1, y1=2, x2=11, y2=12)
```

- [ ] **Step 2: Run failing adapter tests**

Run: `pytest tests/test_engine_adapters.py -v`
Expected: FAIL because adapters do not exist.

- [ ] **Step 3: Implement adapters around existing code**

Adapters should accept concrete legacy objects in their constructor. They should
translate core options into legacy settings without reading global config inside
the adapter method. Where existing legacy code still reads global config, isolate
that in the adapter constructor and mark it as temporary migration debt in one
short comment.

- [ ] **Step 4: Run adapter tests**

Run: `pytest tests/test_engine_adapters.py -v`
Expected: PASS.

---

### Task 5: Page Translation Pipeline Stages

**Files:**
- Create: `backend/pipeline/stages/detection.py`
- Create: `backend/pipeline/stages/ocr.py`
- Create: `backend/pipeline/stages/translation.py`
- Create: `backend/pipeline/stages/inpainting.py`
- Create: `backend/pipeline/stages/layout.py`
- Create: `backend/pipeline/stages/rendering.py`
- Create: `backend/pipeline/planner.py`
- Test: `tests/test_page_translation_pipeline.py`

**Interfaces:**
- Consumes: core ports and strategies.
- Produces: runnable `translate_page` plan using stage artifacts.

- [ ] **Step 1: Write failing pipeline integration test with fake engines**

```python
from pipeline.planner import PipelinePlanner
from pipeline.runner import PipelineRunner


def test_translate_page_pipeline_runs_all_stages(fake_container, fake_pipeline_context):
    plan = PipelinePlanner().translate_page_plan()
    runner = fake_container.pipeline_runner

    result = runner.run(fake_pipeline_context, plan)

    assert result.succeeded
    assert "detection_result" in result.context.artifacts
    assert "ocr_result" in result.context.artifacts
    assert "translation_result" in result.context.artifacts
    assert "render_result" in result.context.artifacts
```

- [ ] **Step 2: Run failing pipeline integration test**

Run: `pytest tests/test_page_translation_pipeline.py -v`
Expected: FAIL because stages do not exist.

- [ ] **Step 3: Implement stages**

Each stage reads the prior artifact, validates it, calls the appropriate core
port, writes its output artifact, and lets the runner record provenance. Stage
names must be:

```text
detection
ocr
translation
inpainting
layout
rendering
```

- [ ] **Step 4: Run pipeline integration test**

Run: `pytest tests/test_page_translation_pipeline.py -v`
Expected: PASS.

---

### Task 6: Container and API Dependency Refactor

**Files:**
- Create: `backend/core/container.py`
- Create: `backend/api/dependencies.py`
- Move/Modify: `backend/routes/*.py` to `backend/api/routes/*.py`
- Move/Modify: route DTOs into `backend/api/schemas/*.py`
- Modify: `backend/main.py`
- Test: `tests/test_api_container_dependencies.py`

**Interfaces:**
- Consumes: ports, adapters, repositories, runner, job manager.
- Produces: `build_container()` and `get_container()`.

- [ ] **Step 1: Write failing API dependency smoke test**

```python
from fastapi.testclient import TestClient
from main import create_app


def test_app_exposes_container_and_settings_route():
    app = create_app()
    client = TestClient(app)

    assert hasattr(app.state, "container")
    response = client.get("/api/settings")
    assert response.status_code == 200
```

- [ ] **Step 2: Run failing smoke test**

Run: `pytest tests/test_api_container_dependencies.py -v`
Expected: FAIL because `create_app` and new dependencies are not wired.

- [ ] **Step 3: Implement container and route dependency injection**

Move routers to `backend/api/routes`. Replace route imports from `core`,
`services.service_registry`, module-level config, and module-level project state
with container dependencies. Keep response shapes compatible with existing
frontend types.

- [ ] **Step 4: Run API smoke test**

Run: `pytest tests/test_api_container_dependencies.py -v`
Expected: PASS.

---

### Task 7: Remove Legacy Singletons and Update Existing Tests

**Files:**
- Remove: `backend/services/service_registry.py`
- Remove route-level page translation wrappers after route migration.
- Remove: `backend/domain/project_state.py` after route migration.
- Modify: `backend/modules/config.py` or leave only a compatibility import during this Big Bang if complete removal breaks external callers.
- Modify: existing tests under `tests/`.

**Interfaces:**
- Consumes: new container, repository, pipeline runner.
- Produces: no direct imports of removed singleton modules from backend application code.

**Progress note, 2026-07-08:**
- `backend/pipeline/page_translation.py` now executes page translation through
  the canonical `PipelineRunner` plan.
- `backend/pipeline/page_translation_stages.py` registers production stages:
  `detection`, `ocr`, `translation`, `inpainting`, `layout`, and `rendering`.
- Single-page and batch translation routes both call the canonical runner
  through `run_page_translation`.
- `tests/test_page_translation_runner.py` asserts that page translation records
  canonical stage provenance and commits the translated page state.
- The inpainting legacy wrapper now receives explicit engine, dilation, and
  bubble-clipping options through `InpaintingService` and
  `InpaintingEngineAdapter` instead of reading the global config singleton.
- The OCR legacy wrapper now receives explicit engine selection through
  `DetectionService` and `OcrEngineAdapter`; `LocalOCR` no longer reads the
  global config singleton to choose Manga OCR vs PPOCR.
- The rendering wrapper now receives explicit min/max font-size options through
  `RenderService`; `TextRenderer` no longer reads the global config singleton
  for font sizing.
- The detection adapter/service path now carries explicit model,
  confidence-threshold, and tiling options into `detect_bubbles`; the RT-DETR
  ONNX detection engine no longer reads the global config singleton for those
  options on the runner path.
- The YOLO ONNX detection engine now receives explicit model,
  confidence-threshold, and tiling options through `initialize` and `detect`
  instead of reading the global config singleton.
- Heuristic detection post-processing now receives explicit bubbles-only,
  line-merge sensitivity, smart-direction, and text-direction override options
  through `DetectionOptions`, `EngineSelectionStrategy`, and the detection
  adapter/service path; `DetectionPipeline` and heuristic line helpers no
  longer read the global config singleton.
- PPOCR and Manga OCR crop preprocessing now receives explicit padding,
  crop-scale, adaptive-binarization, and adaptive-binarization strength options
  through `OcrOptions`, `OcrEngineAdapter`, and `LocalOCR`; the OCR engines no
  longer read the global config singleton for crop preprocessing.
- The composition root now builds a container-owned `AppConfig` instance instead
  of importing the global config singleton, and page translation routes use the
  container-owned canonical pipeline runner.
- `backend/modules/config.py` no longer creates or auto-loads a module-level
  `config` singleton, and model-requirement helpers now require an explicit
  `AppConfig` from the container or CLI composition path.
- `backend/domain/project_state.py` has been removed. API routes now use the
  container-owned `core.state.ProjectState` through `container.project_state`.
- `AppContainer` no longer exposes a duplicate `legacy_state` field or unused
  runtime `project_repository` field.
- Module-level `service = ...Service()` singletons were removed from
  `backend/services`, and `backend/pipeline/page_analysis.py` no longer creates
  module-level service instances at import time.
- `backend/pipeline` no longer imports `backend/services` directly. Page
  translation stages receive analysis, cache, encoding, and review-state
  collaborators from the composition root.
- `backend/pipeline` no longer imports `backend/modules` directly. The page
  translation stage uses an attribute-compatible translation block instead of
  the legacy `modules.utils.textblock.TextBlock`.
- `backend/infrastructure` now exists as a concrete package. Logging setup and
  user-data path helpers moved from `backend/modules` into
  `backend/infrastructure/logging` and `backend/infrastructure/storage`.
- Model download helpers (`ModelDownloader`, `ModelID`, `download_url_to_file`)
  moved from `backend/modules/utils/download*.py` into
  `backend/infrastructure/downloads`. `tests/test_backend_boundaries.py` now
  asserts the legacy download modules stay deleted.
- The image toolkit moved from `backend/imkit` into
  `backend/infrastructure/image` (same `imk` facade, imported as
  `from infrastructure import image as imk`). The only live helper in
  `backend/modules/utils/image_utils.py` (`build_bubble_clip_mask`) moved to
  `backend/infrastructure/image/masks.py`; the rest of that file was dead code
  and was deleted. `tests/test_backend_boundaries.py` asserts the legacy
  modules stay deleted and that `backend/infrastructure` never imports
  `modules`, `services`, `api`, `pipeline`, or `engines`.
- Shared ML runtime helpers (`device`, `onnx`, `torch_autocast`) moved from
  `backend/modules/utils` into `backend/infrastructure/runtime` (facade at
  `infrastructure.runtime`). These are used across the detection, OCR, and
  inpainting engine implementations. The duplicate `modules/utils/paths.py`
  was deleted in favor of the existing `infrastructure/storage/paths.py`
  (`device.py` now imports `get_user_data_dir` from `infrastructure.storage`).
  Remaining `modules/utils` files (`textblock`, `translator_utils`,
  `language_utils`, `platform_utils`, `common_utils`, `exceptions`) are
  engine/domain-coupled and will move with their vertical engine slices.
- The inpainting engine slice moved into `backend/engines/inpainting`:
  `modules/inpainting/{base,lama,aot,mi_gan,schema}.py`,
  `modules/inpainting_wrapper.py` (→ `hybrid.py`, `HybridInpainter`),
  `services/inpainting_service.py` (→ `service.py`, `InpaintingService`), and
  the inpainting-private helper `modules/utils/inpainting.py` (→ `helpers.py`).
  The composition root now wires `InpaintingService` from
  `engines.inpainting.service`. This is the first complete vertical engine
  slice absorbed out of `backend/modules`; detection, OCR, and rendering
  follow the same pattern. Boundary tests assert all legacy inpainting
  locations stay deleted.
- The dead `backend/modules/rendering` package was removed: `render.py` had
  no importers and imported a nonexistent module
  (`app.ui.canvas.text.vertical_layout`), and `hyphen_textwrap.py` was used
  only by that dead file.
- Font resolution moved from `services/font_resolver_service.py` into
  `backend/infrastructure/fonts` (facade `infrastructure.fonts`, singleton
  `resolver` preserved) — it is shared foundation used by both the rendering
  path and `page_export_service`.
- The rendering engine slice moved into `backend/engines/rendering`:
  `services/typesetting_service.py` (→ `typesetting.py`),
  `modules/rendering_wrapper.py` (→ `renderer.py`, `TextRenderer`),
  `services/render_service.py` (→ `service.py`, `RenderService`), and
  `services/layout_planner_service.py` (→ `layout_planner.py`,
  `LayoutPlannerService`) — the last matches the design's explicit mapping.
  The composition root wires `RenderService` and `LayoutPlannerService` from
  `engines.rendering`. `render_service` still imports the `app.models`
  `TextBubble` type (transitional; `app/models.py` is mapped to
  `core/models/*` in a later step). Boundary tests assert the legacy
  rendering locations stay deleted.
- Shared engine domain types moved into `backend/engines/common`:
  `modules/utils/textblock.py` (TextBlock, used by detection/OCR/translation/
  bubble paths) plus its algorithm dependencies `detection/utils/geometry.py`,
  `detection/utils/text_lines.py`, `detection/utils/orientation.py`, and
  `modules/utils/language_utils.py`.
- The detection engine slice moved into `backend/engines/detection`:
  all of `modules/detection/*` (backend, base, factory, pipeline,
  ppocr_lines, processor, rtdetr_v2, rtdetr_v2_onnx, wrapper, yolo_onnx,
  `font/`, `heuristic_lines/`, remaining `utils/`) and
  `services/detection_service.py` (→ `service.py`, `DetectionService`).
  The dead `detection/utils/bubbles.py` (no importers) was deleted.
  `get_app_data_dir` (roaming app-data path) moved into
  `infrastructure/storage`; `modules/config.py` and the detection service
  OCR cache now source it from there. Transitional legacy imports that the
  OCR slice move will remove: `engines/detection/ppocr_lines.py` →
  `modules.ocr.ppocr.{preprocessing,postprocessing,torch}` and
  `engines/detection/service.py` → `modules.ocr_wrapper.LocalOCR`.
- The OCR engine slice moved into `backend/engines/ocr`: `modules/ocr/*`
  (base, `manga_ocr/`, `pororo/`, `ppocr/`) and `modules/ocr_wrapper.py`
  (→ `local.py`, `LocalOCR`). This removed the transitional legacy imports
  in `engines/detection`; `backend/modules` no longer contains any engine
  implementations. Note: the `backend == "torch"` branch in
  `engines/detection/ppocr_lines.py` references `engines.ocr.ppocr.torch`,
  which does not exist in the repo — that branch was equally broken before
  the move (pre-existing dead branch, kept as-is).
- Dead OCR engine variants were deleted after the move: the entire vendored
  `engines/ocr/pororo/` tree (no importers; depends on `wget`, which is in
  no requirements file, and on a `pororo.models.brainOCR` module that does
  not exist in the repo, so it could never import) and the unused
  `manga_ocr/engine.py` (Torch) and `manga_ocr/onnx_engine.py` (int8)
  variants. The live OCR engines are `manga_ocr/mobile/onnx_engine.py` and
  `ppocr/engine.py`, dispatched by `engines/ocr/local.py`. The PORORO /
  MANGA_OCR_BASE / MANGA_OCR_INT8_ONNX entries remain in the download
  registry (data only, no code references).

- [ ] **Step 1: Find remaining forbidden imports**

Run:

```powershell
rg "service_registry|domain.project_state|legacy_state|from modules.config import config" backend tests
```

Expected: list remaining callers to update.

- [ ] **Step 2: Update callers**

Replace remaining application callers with container, repository, settings
snapshot, or explicit options. Existing tests may import fakes directly from new
test fixtures.

- [ ] **Step 3: Run targeted backend tests**

Run:

```powershell
pytest tests/test_page_translation_runner.py tests/test_inpainting_engine_options.py tests/test_ocr_pipeline_options.py tests/test_translation_options.py -v
```

Expected: PASS after tests are updated to new names and injected fakes.

---

### Task 8: Full Verification and Documentation Update

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-07-backend-composition-root-design.md` if final implementation differs.

**Interfaces:**
- Consumes: completed refactor.
- Produces: passing verification and updated architecture docs.

- [x] **Step 1: Run full tests**

Run: `pytest -v`
Expected: PASS.

- [x] **Step 2: Run import boundary checks**

Run:

```powershell
rg "from engines|import engines" backend/pipeline backend/api
rg "service_registry|state = ProjectState\\(|config: AppConfig = AppConfig\\(" backend
```

Expected: first command finds no pipeline/API imports of concrete engines;
second command finds no active legacy singleton definitions.

- [x] **Step 3: Update README architecture section**

Replace the backend bullet with the new layer description and mention that the
pipeline uses injected ports, strategies, validation, and provenance.

- [x] **Step 4: Commit**

Run:

```powershell
git add backend tests README.md docs/superpowers
git commit -m "refactor: introduce backend composition root architecture"
```

Expected: commit succeeds once local Git user identity is configured.

Verification result:

- `python -m pytest -q`: 76 passed.
- `rg "from engines|import engines" backend/pipeline backend/api`: no matches.
- `rg "service_registry|state = ProjectState\\(|config: AppConfig = AppConfig\\(" backend`: no matches.
- Extended singleton scan for direct `modules.config config`, legacy `load_settings`/`save_settings`, adaptive-binarization alias, and global `ProjectState`: no matches.

Documentation follow-up, 2026-07-08:

- `docs/backend-dependency-contract.md` is now the operational dependency
  contract for layer ownership, forbidden coupling, runtime entry points,
  dependency sets, and boundary-check commands.
- `README.md` Quick Start now documents the real desktop launch path:
  `npm run dev` -> `tauri dev` -> Vite frontend plus Python backend from the
  repository-root `venv/`.
- Standalone `npm --prefix frontend run dev` is documented as static UI work
  only because it does not launch the backend or provide the Tauri command
  bridge.

Architecture cleanup pivot, 2026-07-08:

- The priority is no longer to keep compatibility wrappers alive. The goal is
  to remove legacy/dead/hard-coded paths until the app runs through the new
  architecture only.
- The old page translation wrapper module was removed. Single-page and batch
  translation routes now call the canonical `PipelineRunner` plan.
- Page analysis helpers moved to `backend/pipeline/page_analysis.py`; production
  stages no longer import an old wrapper module for helper behavior.
- Unused desktop/frontend command surfaces for the old page translation path
  were removed.
- Remaining cleanup targets include continuing to absorb transitional
  `backend/modules` wrappers behind `backend/engines` or
  `backend/infrastructure`, and moving hard-coded defaults behind strategies or
  explicit container-owned options.

---

## Self-Review

- Spec coverage: The plan covers composition root, API dependencies, ports,
  pipeline runner, strategies, validation, provenance, engine adapters,
  infrastructure boundaries, route migration, tests, and completion checks.
- Placeholder scan: No `TBD`, `TODO`, or unnamed implementation steps remain.
- Type consistency: The plan consistently uses `AppContainer`,
  `PipelineContext`, `PipelinePlan`, `PipelineRunner`, `StageRegistry`, and core
  port names defined in earlier tasks.
