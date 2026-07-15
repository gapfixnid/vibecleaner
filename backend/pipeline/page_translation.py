from __future__ import annotations

import os
from time import perf_counter
from typing import Any

from ..core.models.image import ImageData
from ..infrastructure.storage.paths import get_app_data_dir
from .context import PipelineContext
from .dag import DagPipelineExecutor
from .telemetry import DEFAULT_TELEMETRY_FILENAME
from .telemetry import JsonlTelemetrySink
from .telemetry import PipelineTelemetryRecord


def _telemetry_stages(context: PipelineContext) -> dict[str, dict[str, Any]]:
    return {
        entry.stage: {
            "engine": entry.engine,
            "duration_ms": entry.duration_ms,
            "warning_count": len(entry.warnings),
            "error_count": len(entry.errors),
        }
        for entry in context.provenance.stages
    }


def _telemetry_quality_scores(context: PipelineContext) -> dict[str, dict[str, Any]]:
    scores = context.artifacts.get("quality_scores", {})
    return {
        stage: {
            "score": float(score.score),
            "passed": bool(score.passed),
            "signals": dict(score.signals),
            "recommended_action": score.recommended_action,
        }
        for stage, score in scores.items()
    }


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
        telemetry_path = os.path.join(get_app_data_dir(), DEFAULT_TELEMETRY_FILENAME)
    telemetry_sink = JsonlTelemetrySink(telemetry_path)
    context.pipeline_variant = "v2"
    started = perf_counter()
    result = DagPipelineExecutor(
        runner.registry, checkpoint_store=checkpoint_store
    ).run(context, planner.translate_page_dag_plan(), resume_manifest=resume_manifest)
    telemetry_sink.record(PipelineTelemetryRecord(
        schema_version=2,
        run_id=str(result.context.provenance.run_id),
        page_id=page_id,
        succeeded=bool(result.succeeded),
        duration_ms=(perf_counter() - started) * 1000,
        stages=_telemetry_stages(result.context),
        quality_scores=_telemetry_quality_scores(result.context),
        quality_replans=list(result.context.artifacts.get("quality_replans", [])),
        errors=[getattr(issue, "message", str(issue)) for issue in result.issues],
        metadata={
            "pipeline": "page_translation",
            "ocr_provenance": result.context.artifacts.get("ocr_provenance", {}),
        },
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
