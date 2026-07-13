# Shadow benchmark

Set `pipeline_v2_shadow` to `true` to run the non-primary pipeline on a copied
context and record a comparison after each page translation. The default output
is `%APPDATA%/vibecleaner/pipeline_shadow_benchmark.jsonl` on Windows.

Set `pipeline_benchmark_path` in the runtime config to override the location.
The file is JSONL, so each line is an independent comparison record suitable
for CI or a later metrics importer. Shadow execution never replaces the
primary result.
