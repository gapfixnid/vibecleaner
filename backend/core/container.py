from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.config import AppConfigSnapshot
from core.state.project_state import ProjectState
from pipeline.planner import PipelinePlanner
from pipeline.registry import StageRegistry
from pipeline.runner import PipelineRunner


@dataclass
class AppContainer:
    config: Any
    project_state: ProjectState
    job_manager: Any
    translation_service: Any
    detection_service: Any
    inpainting_service: Any
    render_service: Any
    export_service: Any
    settings: AppConfigSnapshot
    stage_registry: StageRegistry
    pipeline_runner: PipelineRunner
    pipeline_planner: PipelinePlanner


def build_container(config: Any | None = None) -> AppContainer:
    from modules.config import AppConfig
    from pipeline.page_translation_stages import build_page_translation_runner
    from services.job_service import job_manager
    from services.detection_service import DetectionService
    from services.export_service import ExportService
    from services.inpainting_service import InpaintingService
    from services.render_service import RenderService
    from services.translation_service import TranslationService

    runtime_config = config or AppConfig()
    if config is None:
        runtime_config.load()

    translation_service = TranslationService(config=runtime_config)
    detection_service = DetectionService(config=runtime_config)
    inpainting_service = InpaintingService(config=runtime_config)
    render_service = RenderService(config=runtime_config)
    export_service = ExportService(render_service)

    settings = AppConfigSnapshot.from_object(runtime_config)
    pipeline_runner = build_page_translation_runner(
        detection_service=detection_service,
        inpainting_service=inpainting_service,
        translation_service=translation_service,
    )

    return AppContainer(
        config=runtime_config,
        project_state=ProjectState(),
        job_manager=job_manager,
        translation_service=translation_service,
        detection_service=detection_service,
        inpainting_service=inpainting_service,
        render_service=render_service,
        export_service=export_service,
        settings=settings,
        stage_registry=pipeline_runner.registry,
        pipeline_runner=pipeline_runner,
        pipeline_planner=PipelinePlanner(),
    )
