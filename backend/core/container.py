from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.config import AppConfigSnapshot
from core.state.project_state import ProjectState as NewProjectState
from core.state.repository import InMemoryProjectRepository
from pipeline.planner import PipelinePlanner
from pipeline.registry import StageRegistry
from pipeline.runner import PipelineRunner
from pipeline.stages import (
    DetectionStage,
    InpaintingStage,
    LayoutStage,
    OcrStage,
    RenderingStage,
    TranslationStage,
)
from pipeline.strategies.engine_selection import EngineSelectionStrategy


@dataclass
class AppContainer:
    config: Any
    legacy_state: Any
    job_manager: Any
    translation_service: Any
    auto_typeset_pipeline: Any
    detection_service: Any
    inpainting_service: Any
    render_service: Any
    export_service: Any
    settings: AppConfigSnapshot
    project_state: NewProjectState
    project_repository: InMemoryProjectRepository
    stage_registry: StageRegistry
    pipeline_runner: PipelineRunner
    pipeline_planner: PipelinePlanner


def build_container() -> AppContainer:
    # Existing services still own the concrete model wrappers during the first
    # composition-root pass; later tasks replace these with direct adapters.
    from engines.detection.adapter import DetectionEngineAdapter
    from engines.inpainting.adapter import InpaintingEngineAdapter
    from engines.ocr.adapter import OcrEngineAdapter
    from engines.rendering.adapter import RenderingEngineAdapter
    from engines.translation.adapter import TranslationEngineAdapter
    from modules.config import config
    from domain.project_state import ProjectState
    from pipeline.auto_typeset import AutoTypesetPipeline
    from services.job_service import job_manager
    from services.detection_service import DetectionService
    from services.export_service import ExportService
    from services.inpainting_service import InpaintingService
    from services.render_service import RenderService
    from services.translation_service import TranslationService

    translation_service = TranslationService(config=config)
    detection_service = DetectionService()
    inpainting_service = InpaintingService(config=config)
    render_service = RenderService()
    export_service = ExportService(render_service)

    settings = AppConfigSnapshot.from_object(config)
    strategy = EngineSelectionStrategy()
    registry = StageRegistry()

    registry.register(DetectionStage(DetectionEngineAdapter(detection_service), strategy))
    registry.register(OcrStage(OcrEngineAdapter(detection_service), strategy))
    registry.register(TranslationStage(TranslationEngineAdapter(translation_service), strategy))
    registry.register(InpaintingStage(InpaintingEngineAdapter(inpainting_service), strategy))
    registry.register(LayoutStage())
    registry.register(RenderingStage(RenderingEngineAdapter(render_service), strategy))

    state = ProjectState()
    project_state = NewProjectState()
    return AppContainer(
        config=config,
        legacy_state=state,
        job_manager=job_manager,
        translation_service=translation_service,
        auto_typeset_pipeline=AutoTypesetPipeline(
            state=state,
            config=config,
            job_manager=job_manager,
            detection_service=detection_service,
            inpainting_service=inpainting_service,
            translation_service=translation_service,
        ),
        detection_service=detection_service,
        inpainting_service=inpainting_service,
        render_service=render_service,
        export_service=export_service,
        settings=settings,
        project_state=project_state,
        project_repository=InMemoryProjectRepository(project_state),
        stage_registry=registry,
        pipeline_runner=PipelineRunner(registry),
        pipeline_planner=PipelinePlanner(),
    )
