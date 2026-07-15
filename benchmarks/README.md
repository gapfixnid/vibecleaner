# Benchmarks

The current benchmark set measures scheduler behavior and detection quality.
The v2 pipeline is the only page translation runtime; legacy fixtures are kept
only where a test explicitly covers a data or adapter boundary.

`scripts/benchmark_pipeline_scheduler.py` is a dependency-free scheduler smoke
benchmark. It measures orchestration overhead only; it is not a claim about OCR,
translation, inpainting, or end-to-end product performance.

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

Evaluate detection recall and split/merge errors with a box-only corpus:

```powershell
python scripts/benchmark_detection_recall.py `
  tests/fixtures/detection_synthetic_corpus.json `
  --output benchmarks/results/detection-synthetic.json
```

The detection corpus stores boxes rather than source images, so it can be used
with synthetic data, licensed annotations, or predictions captured from a
local model run without adding image assets to the repository.
