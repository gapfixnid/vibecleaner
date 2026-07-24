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
from .validation.results import PipelineJobError
from .dag import _stable_digest


def _telemetry_stages(context: PipelineContext) -> dict[str, dict[str, Any]]:
    quality_replans = context.artifacts.get("quality_replans", [])
    ocr_provenance = context.artifacts.get("ocr_provenance", {})
    ocr_cache = ocr_provenance.get("cache", {}) if isinstance(ocr_provenance, dict) else {}
    return {
        entry.stage: {
            "engine": entry.engine,
            "duration_ms": entry.duration_ms,
            "warning_count": len(entry.warnings),
            "error_count": len(entry.errors),
            "retry_count": int(entry.options.get("retry_count", 0)),
            "resource": entry.options.get("resource"),
            "cache_hits": (
                int(ocr_cache.get("hits_after", 0)) - int(ocr_cache.get("hits_before", 0))
                if entry.stage == "ocr" and ocr_cache.get("hits_before") is not None
                and ocr_cache.get("hits_after") is not None else None
            ),
            "cache_misses": (
                int(ocr_cache.get("misses_after", 0)) - int(ocr_cache.get("misses_before", 0))
                if entry.stage == "ocr" and ocr_cache.get("misses_before") is not None
                and ocr_cache.get("misses_after") is not None else None
            ),
            "replan_count": sum(1 for item in quality_replans if item.get("stage") == entry.stage),
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


def _telemetry_runtime_providers(context: PipelineContext) -> dict[str, list[str]]:
    diagnostics = context.artifacts.get("runtime_provider_diagnostics", {})
    if not isinstance(diagnostics, dict):
        return {}
    return {
        stage: list(values)
        for stage, values in diagnostics.items()
        if isinstance(values, (list, tuple))
    }


def _runtime_provider_diagnostics(runner: Any) -> dict[str, list[str]]:
    mapping = {
        "detection": ("detection", "detection_service", "get_diagnostics"),
        "ocr": ("ocr", "detection_service", "get_diagnostics"),
        "inpainting": ("inpainting", "inpainting_service", "runtime_status"),
    }
    result: dict[str, list[str]] = {}
    for label, (stage_name, service_attr, method_name) in mapping.items():
        try:
            service = getattr(runner.registry.get(stage_name), service_attr)
            diagnostics = getattr(service, method_name)()
            key = "detector_execution_providers" if label == "detection" else (
                "ocr_execution_providers" if label == "ocr" else "execution_providers"
            )
            providers = diagnostics.get(key, []) if isinstance(diagnostics, dict) else []
            if providers:
                result[label] = [str(provider) for provider in providers]
        except Exception:
            continue
    return result


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
    # Capture the input identity under the project lock before any stage can
    # mutate the page. Detection later validates this identity; it must not
    # create a new one after checkpoint hydration.
    with state.lock:
        page = next((item for item in state.pages if item.page_id == page_id), None)
        if page is None:
            raise ValueError(f"Page not found: {page_id}")
        project_generation = state.project_generation
        visual_revision = page.visual_revision
        image_visual_revision = page.image_visual_revision
        model_values = {
            name: getattr(config, name, None)
            for name in ("detect_model", "ocr_model", "translation_model", "inpainting_model", "inpainting_engine")
        }
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
            "runtime_provider_diagnostics": _runtime_provider_diagnostics(runner),
            "project_generation": project_generation,
            "visual_revision": visual_revision,
            "image_visual_revision": image_visual_revision,
            "model_digest": model_values,
            "settings_digest": _stable_digest(config),
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
            "runtime_providers": _telemetry_runtime_providers(result.context),
            "quality_aggregates": dict(
                result.context.artifacts.get(
                    "quality_aggregates", {}
                )
            ),
        },
    ))
    runner.last_result = result
    if not result.succeeded:
        issue = result.issues[0] if result.issues else None
        if issue is None:
            raise RuntimeError("Page translation pipeline failed")
        raise PipelineJobError(issue)
    if checkpoint_store is not None:
        delete = getattr(checkpoint_store, "delete", None)
        if callable(delete):
            if resume_manifest is not None:
                delete(resume_manifest.run_id)
            delete(result.context.provenance.run_id)
    return result.context.artifacts["result"]
