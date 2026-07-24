#!/usr/bin/env python3
"""Evaluate a licensed/synthetic quality corpus and write only observed metrics."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.pipeline.quality_evaluation import evaluate_quality_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.corpus.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        payload = {"cases": payload}
    if not isinstance(payload, dict) or not isinstance(payload.get("cases", []), list):
        raise ValueError("Quality corpus must be an object with a cases list")
    result = evaluate_quality_corpus(payload)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
