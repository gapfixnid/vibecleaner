#!/usr/bin/env python3
"""Aggregate shadow benchmark JSONL and render a self-contained HTML report."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from scripts.evaluate_pipeline_rollout import load_jsonl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from evaluate_pipeline_rollout import load_jsonl


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _rate(values: list[bool]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    metadata = [row.get("metadata") or {} for row in records]
    return {
        "sample_count": len(records),
        "success_rate": _rate([
            bool(row.get("primary_succeeded")) and bool(row.get("shadow_succeeded"))
            for row in records
        ]),
        "equivalence_rate": _rate([bool(row.get("equivalent")) for row in records]),
        "ocr_text_match_mean": _mean([
            float(item["ocr_text_match_ratio"])
            for item in metadata if item.get("ocr_text_match_ratio") is not None
        ]),
        "translation_match_mean": _mean([
            float(item["translation_match_ratio"])
            for item in metadata if item.get("translation_match_ratio") is not None
        ]),
        "primary_duration_ms_mean": _mean([
            float(row["primary_duration_ms"])
            for row in records if row.get("primary_duration_ms") is not None
        ]),
        "shadow_duration_ms_mean": _mean([
            float(row["shadow_duration_ms"])
            for row in records if row.get("shadow_duration_ms") is not None
        ]),
    }


def aggregate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        recorded_at = str(row.get("recorded_at", "unknown"))
        try:
            key = datetime.fromisoformat(recorded_at.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            key = "unknown"
        groups[key].append(row)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "overall": _metrics(records),
        "by_date": {key: _metrics(groups[key]) for key in sorted(groups)},
    }


def render_dashboard(summary: dict[str, Any]) -> str:
    metrics = summary["overall"]
    cards = "".join(
        f'<div class="card"><span>{html.escape(label)}</span><strong>{html.escape(str(metrics.get(key) if metrics.get(key) is not None else "n/a"))}</strong></div>'
        for key, label in (
            ("sample_count", "Samples"),
            ("success_rate", "Success rate"),
            ("equivalence_rate", "Equivalence"),
            ("ocr_text_match_mean", "OCR match"),
            ("translation_match_mean", "Translation match"),
        )
    )
    rows = []
    for date, values in summary["by_date"].items():
        rows.append(
            "<tr>" + "".join(f"<td>{html.escape(str(values.get(key) if values.get(key) is not None else 'n/a'))}</td>" for key in (
                "sample_count", "success_rate", "equivalence_rate", "ocr_text_match_mean", "translation_match_mean",
            )) + f"<td>{html.escape(date)}</td></tr>"
        )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>VibeCleaner Pipeline Benchmark</title><style>
body{font:14px system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#202124;background:#fafafa}
h1{font-size:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.card{background:white;border:1px solid #ddd;border-radius:8px;padding:14px}.card span{display:block;color:#666}.card strong{display:block;font-size:24px;margin-top:8px}table{border-collapse:collapse;width:100%;margin-top:24px;background:white}th,td{border:1px solid #ddd;padding:9px;text-align:right}th:last-child,td:last-child{text-align:left}th{background:#f0f2f5}
</style></head><body><h1>VibeCleaner Pipeline Benchmark</h1>
<div class="grid">""" + cards + """</div><table><thead><tr><th>Samples</th><th>Success</th><th>Equivalence</th><th>OCR</th><th>Translation</th><th>Date</th></tr></thead><tbody>""" + "".join(rows) + """</tbody></table></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()
    if not args.path.exists():
        if not args.allow_missing:
            raise SystemExit(f"Benchmark file does not exist: {args.path}")
        records: list[dict[str, Any]] = []
    else:
        records = load_jsonl(args.path)
    summary = aggregate_records(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_dashboard(summary), encoding="utf-8")
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
