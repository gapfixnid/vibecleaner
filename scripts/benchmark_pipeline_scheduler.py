#!/usr/bin/env python3
"""Measure Pipeline v1 orchestration overhead with dependency-free no-op stages."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.models.image import ImageData
from backend.core.models.page import MangaPage
from backend.pipeline.context import PipelineContext
from backend.pipeline.plan import PipelinePlan
from backend.pipeline.registry import StageRegistry
from backend.pipeline.runner import PipelineRunner


STAGES = ["detection", "ocr", "translation", "inpainting", "layout", "rendering"]


class NoOpStage:
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, context: PipelineContext) -> PipelineContext:
        context.artifacts[self.name] = True
        return context


def _revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * fraction))
    return ordered[index]


def _run_once(runner: PipelineRunner, plan: PipelinePlan) -> float:
    context = PipelineContext(
        page_id="scheduler-smoke",
        page=MangaPage(file_path="benchmark.png", page_id="scheduler-smoke"),
        image=ImageData(array=None, explicit_width=1, explicit_height=1),
        settings={},
    )
    started = perf_counter_ns()
    result = runner.run(context, plan)
    elapsed_us = (perf_counter_ns() - started) / 1_000
    if not result.succeeded or list(result.context.artifacts) != STAGES:
        raise RuntimeError("scheduler smoke workload changed unexpectedly")
    return elapsed_us


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations < 1 or args.warmup < 0:
        parser.error("iterations must be positive and warmup must be non-negative")

    registry = StageRegistry()
    for stage in STAGES:
        registry.register(NoOpStage(stage))
    runner = PipelineRunner(registry)
    plan = PipelinePlan(stages=STAGES)

    for _ in range(args.warmup):
        _run_once(runner, plan)
    samples = [_run_once(runner, plan) for _ in range(args.iterations)]

    result = {
        "schema_version": 1,
        "benchmark": "pipeline-scheduler-smoke",
        "pipeline": "v1",
        "disclaimer": "No-op orchestration overhead only; not end-to-end performance.",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "revision": _revision(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "workload": {
            "execution_model": "sequential",
            "stages": STAGES,
            "iterations": args.iterations,
            "warmup": args.warmup,
        },
        "metrics_us": {
            "mean": round(statistics.fmean(samples), 3),
            "p50": round(statistics.median(samples), 3),
            "p95": round(_percentile(samples, 0.95), 3),
            "min": round(min(samples), 3),
            "max": round(max(samples), 3),
        },
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
