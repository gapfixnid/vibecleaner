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

For a local licensed-image corpus, add `image_path` to each case and capture
RT-DETR predictions before evaluation:

```powershell
python scripts/capture_detection_predictions.py `
  path/to/detection-corpus.json `
  --output benchmarks/results/detection-rtdetr.json

python scripts/benchmark_detection_recall.py `
  benchmarks/results/detection-rtdetr.json
```

The capture output includes the model, threshold, tiling setting, predicted
boxes, and raw model confidence values used for the run.

## Golden image and resource regression

`tests/fixtures/golden_image_corpus.json` is a deterministic, repository-safe
fixture catalog covering manga, webtoon, long-page, low-contrast, SFX, blank,
and Unicode cases. It does not claim model accuracy. Run the boundary and
resource benchmark with:

```powershell
python scripts/benchmark_golden_regression.py `
  --output benchmarks/results/golden-regression.json `
  --repeat 3
```

Pass a previous result with `--baseline` to fail when a case's p50/p95 input
validation time or peak Python allocation grows by more than 25 percent. The
output is machine-readable and should be retained as a CI artifact, not
committed as a hardware-independent golden timing value.

If ground-truth coordinates are not known, create them with the temporary
local annotator. It is not included in the product UI or release package:

```powershell
python scripts/annotate_detection_corpus.py `
  path/to/image-folder `
  --output path/to/detection-corpus.json
```

Left-drag each text region, press `Enter` or `Right Arrow` for the next image,
and use `U` to undo, `C` to clear, and `S` to save. The saved coordinates are
original image pixels and can be passed to the capture command above.
