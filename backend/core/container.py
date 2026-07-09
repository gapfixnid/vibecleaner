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
    cache_tasks: Any
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
    from core.config import AppConfig
    from infrastructure.storage import get_settings_file_path
    from pipeline.page_translation_stages import build_page_translation_runner
    from infrastructure.cache.tasks import CacheTaskQueue
    from infrastructure.jobs import JobManager
    from pipeline.analysis.bubbles import BubbleAnalysisService
    from engines.detection.service import DetectionService
    from engines.rendering.export import ExportService
    from infrastructure.image.encoding import encode_preview_jpeg_bytes, encode_thumbnail_bytes
    from engines.inpainting.service import InpaintingService
    from engines.rendering.layout_planner import LayoutPlannerService
    from pipeline.analysis.page import PageAnalysisService
    from infrastructure.image.loading import ensure_page_image, invalidate_page_caches
    from engines.rendering.service import RenderService
    from core.state.review import refresh_page_status
    from engines.translation.service import TranslationService

    runtime_config = config or AppConfig(settings_path=get_settings_file_path())
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
        page_analysis_service=PageAnalysisService(),
        bubble_analysis_service=BubbleAnalysisService(),
        layout_planner_service=LayoutPlannerService(),
        ensure_page_image=ensure_page_image,
        invalidate_page_caches=invalidate_page_caches,
        encode_preview_jpeg_bytes=encode_preview_jpeg_bytes,
        encode_thumbnail_bytes=encode_thumbnail_bytes,
        refresh_page_status=refresh_page_status,
    )

    return AppContainer(
        config=runtime_config,
        project_state=ProjectState(),
        job_manager=JobManager(),
        cache_tasks=CacheTaskQueue(),
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
