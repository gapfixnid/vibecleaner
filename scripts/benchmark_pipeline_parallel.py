#!/usr/bin/env python3
"""Compare sequential v1 and dependency-parallel v2 scheduler wall time."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter, sleep
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.pipeline.dag import DagPipelineExecutor, DagPipelinePlan, DagStage
from backend.pipeline.provenance import ProvenanceTrace
from backend.pipeline.registry import StageRegistry
from backend.pipeline.resources import ResourceClass


class DelayStage:
    def __init__(self, name: str, delay: float = 0.0) -> None:
        self.name = name
        self.delay = delay

    def run(self, context):
        sleep(self.delay)
        context.artifacts[self.name] = True
        return context


def _context():
    return SimpleNamespace(artifacts={}, provenance=ProvenanceTrace(), page_id="benchmark")


def run_benchmark(*, delay_seconds: float = 0.04, iterations: int = 10) -> dict:
    registry = StageRegistry()
    registry.register(DelayStage("ocr"))
    registry.register(DelayStage("translation", delay_seconds))
    registry.register(DelayStage("inpainting", delay_seconds))
    registry.register(DelayStage("layout"))
    sequential = DagPipelinePlan((
        DagStage("ocr"),
        DagStage("translation", ("ocr",)),
        DagStage("inpainting", ("translation",)),
        DagStage("layout", ("inpainting",)),
    ))
    parallel = DagPipelinePlan((
        DagStage("ocr"),
        DagStage("translation", ("ocr",), ResourceClass.NETWORK, parallel_safe=True),
        DagStage("inpainting", ("ocr",), ResourceClass.GPU, parallel_safe=True),
        DagStage("layout", ("translation", "inpainting")),
    ))
    executor = DagPipelineExecutor(registry)

    def samples(plan):
        values = []
        for _ in range(iterations):
            started = perf_counter()
            result = executor.run(_context(), plan)
            if not result.succeeded:
                raise RuntimeError("scheduler benchmark failed")
            values.append((perf_counter() - started) * 1000)
        return values

    v1 = samples(sequential)
    v2 = samples(parallel)
    v1_mean = statistics.fmean(v1)
    v2_mean = statistics.fmean(v2)
    return {
        "schema_version": 1,
        "benchmark": "pipeline-independent-stage-parallelism",
        "iterations": iterations,
        "delay_seconds_per_independent_stage": delay_seconds,
        "v1_mean_ms": round(v1_mean, 3),
        "v2_mean_ms": round(v2_mean, 3),
        "speedup": round(v1_mean / v2_mean, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.04)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_benchmark(delay_seconds=args.delay, iterations=args.iterations)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
