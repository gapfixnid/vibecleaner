# Benchmarks

Phase A freezes two different baselines before Pipeline v2 work starts:

1. `tests/fixtures/pipeline_v1/contract.json` is the behavioral contract for
   the current user-facing page pipeline. Tests must keep it green while v2 is
   developed beside v1.
2. `scripts/benchmark_pipeline_scheduler.py` is a dependency-free scheduler
   smoke benchmark. It measures orchestration overhead only; it is not a claim
   about OCR, translation, inpainting, or end-to-end product performance.

Generate a local scheduler baseline from the repository root:

```powershell
python scripts/benchmark_pipeline_scheduler.py `
  --output benchmarks/results/pipeline-v1-scheduler.json
```

Results under `benchmarks/results/` are intentionally ignored because timings
are machine-specific. CI may retain them as artifacts and compare v1/v2 on the
same runner. Product quality/performance baselines require a licensed dataset,
pinned model catalog, and hardware profile; those arrive with the benchmark
workstream rather than being fabricated in Phase A.

Verify that v2 still overlaps independent Network and GPU stages:

```powershell
python scripts/benchmark_pipeline_parallel.py `
  --output benchmarks/results/pipeline-v2-parallel.json
```

The corresponding CI test uses deterministic delay stages and requires at
least a 1.5x wall-clock speedup over the equivalent sequential dependency chain.
