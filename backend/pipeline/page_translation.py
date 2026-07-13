from __future__ import annotations

import os
from typing import Any

from ..core.models.image import ImageData
from ..infrastructure.storage.paths import get_app_data_dir
from .benchmark import JsonlBenchmarkSink
from .context import PipelineContext
from .dag import DagPipelineExecutor
from .rollout import PipelineExecutionCoordinator, PipelineRollout
from .shadow import clone_page_translation_context, clone_page_translation_fallback_context


def run_page_translation(
    *,
    job: dict,
    page_id: str,
    state: Any,
    config: Any,
    job_manager: Any,
    runner: Any,
    planner: Any,
    show_progress: bool = True,
) -> dict[str, int]:
    context = PipelineContext(
        page_id=page_id,
        page=None,
        image=ImageData(array=None),
        settings=config,
        artifacts={
            "job": job,
            "show_progress": show_progress,
            "state": state,
            "config": config,
            "job_manager": job_manager,
        },
    )
    plan = planner.translate_page_plan()
    rollout = PipelineRollout.from_settings(config)
    benchmark_sink = None
    if rollout.shadow:
        benchmark_path = getattr(config, "pipeline_benchmark_path", None)
        if not benchmark_path:
            benchmark_path = os.path.join(get_app_data_dir(), "pipeline_shadow_benchmark.jsonl")
        benchmark_sink = JsonlBenchmarkSink(benchmark_path)
    coordinator = PipelineExecutionCoordinator(
        v1_runner=lambda item: runner.run(item, plan),
        v2_runner=lambda item: DagPipelineExecutor(runner.registry).run(
            item, planner.translate_page_dag_plan()
        ),
        benchmark_sink=benchmark_sink,
        shadow_context_factory=clone_page_translation_context,
        fallback_context_factory=clone_page_translation_fallback_context,
    )
    result = coordinator.run(context, rollout)
    runner.last_result = result
    if not result.succeeded:
        message = result.issues[0].message if result.issues else "Page translation pipeline failed"
        raise RuntimeError(message)
    return result.context.artifacts["result"]
