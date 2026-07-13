from __future__ import annotations

from typing import Any

from ..core.models.image import ImageData
from .context import PipelineContext
from .dag import DagPipelineExecutor, DagPipelinePlan, DagStage
from .rollout import PipelineExecutionCoordinator, PipelineRollout


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
    coordinator = PipelineExecutionCoordinator(
        v1_runner=lambda item: runner.run(item, plan),
        v2_runner=lambda item: DagPipelineExecutor(runner.registry).run(
            item,
            DagPipelinePlan(
                tuple(
                    DagStage(name, (plan.stages[index - 1],) if index else ())
                    for index, name in enumerate(plan.stages)
                )
            ),
        ),
    )
    result = coordinator.run(context, rollout)
    runner.last_result = result
    if not result.succeeded:
        message = result.issues[0].message if result.issues else "Page translation pipeline failed"
        raise RuntimeError(message)
    return result.context.artifacts["result"]
