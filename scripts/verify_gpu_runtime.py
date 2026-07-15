#!/usr/bin/env python3
"""Verify CUDA provider loading and run one inference per installed ONNX model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np

# Allow direct execution with ``python scripts/verify_gpu_runtime.py``.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.infrastructure.downloads import models_base_dir
from backend.infrastructure.runtime.device import get_providers
from backend.infrastructure.runtime.onnx import make_session


def _dimension(value: object, *, index: int, rank: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if rank == 4:
        return (1, 3, 640, 640)[index]
    return 1


def _input_array(input_meta: object) -> np.ndarray:
    shape = list(getattr(input_meta, "shape", (1,)))
    rank = len(shape)
    name = getattr(input_meta, "name", "").lower()
    defaults = (1, 1, 640, 640) if "mask" in name else (1, 3, 640, 640)
    resolved = [
        defaults[index] if value is None and rank == 4 else _dimension(value, index=index, rank=rank)
        for index, value in enumerate(shape)
    ]
    type_name = getattr(input_meta, "type", "tensor(float)")
    dtype = {
        "tensor(float)": np.float32,
        "tensor(float16)": np.float16,
        "tensor(double)": np.float64,
        "tensor(int64)": np.int64,
        "tensor(int32)": np.int32,
        "tensor(uint8)": np.uint8,
        "tensor(bool)": np.bool_,
    }.get(type_name)
    if dtype is None:
        raise ValueError(f"Unsupported ONNX input type: {type_name}")
    return np.zeros(resolved, dtype=dtype)


def verify_model(path: Path, providers: list[object]) -> dict[str, object]:
    session = make_session(str(path), providers=providers)
    inputs = {meta.name: _input_array(meta) for meta in session.get_inputs()}
    started = perf_counter()
    session.run(None, inputs)
    elapsed_ms = (perf_counter() - started) * 1000
    return {
        "model": str(path),
        "session_providers": session.get_providers(),
        "input_shapes": {
            meta.name: {"shape": list(meta.shape), "type": meta.type}
            for meta in session.get_inputs()
        },
        "inference_ms": round(elapsed_ms, 2),
        "cuda_used": "CUDAExecutionProvider" in session.get_providers(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", type=Path)
    args = parser.parse_args()
    providers = get_providers("cuda")
    if "CUDAExecutionProvider" not in providers:
        raise SystemExit(f"CUDAExecutionProvider is unavailable: {providers}")
    default_models = (
        Path(models_base_dir) / "detection" / "detector.onnx",
        Path(models_base_dir) / "inpainting" / "lama-manga-dynamic.onnx",
    )
    models = args.model or default_models
    results = [verify_model(path, providers) for path in models if path.exists()]
    if not results:
        raise SystemExit("No requested ONNX model files were found")
    print(json.dumps({"requested_providers": providers, "models": results}, indent=2))
    if not all(bool(result["cuda_used"]) for result in results):
        raise SystemExit("At least one ONNX session did not use CUDA")


if __name__ == "__main__":
    main()
