from __future__ import annotations

import os
from time import perf_counter
from typing import Any

from ..core.models.image import ImageData
from ..infrastructure.storage.paths import get_app_data_dir
from .context import PipelineContext
from .dag import DagPipelineExecutor
from .telemetry import JsonlTelemetrySink
from .telemetry import PipelineTelemetryRecord


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
    checkpoint_store: Any | None = None,
    resume_manifest: Any | None = None,
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
    telemetry_path = getattr(config, "pipeline_telemetry_path", None)
    if not telemetry_path:
        telemetry_path = os.path.join(get_app_data_dir(), "pipeline_rollout_telemetry.jsonl")
    telemetry_sink = JsonlTelemetrySink(telemetry_path)
    context.pipeline_variant = "v2"
    started = perf_counter()
    result = DagPipelineExecutor(
        runner.registry, checkpoint_store=checkpoint_store
    ).run(context, planner.translate_page_dag_plan(), resume_manifest=resume_manifest)
    telemetry_sink.record(PipelineTelemetryRecord(
        run_id=str(result.context.provenance.run_id),
        page_id=page_id,
        primary="v2",
        primary_succeeded=bool(result.succeeded),
        returned_variant="v2",
        fallback_attempted=False,
        fallback_used=False,
        fallback_succeeded=None,
        shadow_enabled=False,
        shadow_succeeded=None,
        primary_error=(
            getattr(result.issues[0], "message", str(result.issues[0]))
            if result.issues else None
        ),
        primary_duration_ms=(perf_counter() - started) * 1000,
    ))
    runner.last_result = result
    if not result.succeeded:
        message = result.issues[0].message if result.issues else "Page translation pipeline failed"
        raise RuntimeError(message)
    if checkpoint_store is not None:
        delete = getattr(checkpoint_store, "delete", None)
        if callable(delete):
            if resume_manifest is not None:
                delete(resume_manifest.run_id)
            delete(result.context.provenance.run_id)
    return result.context.artifacts["result"]
