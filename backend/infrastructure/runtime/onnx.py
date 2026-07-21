from __future__ import annotations

import os
from typing import Any, Optional
import onnxruntime as ort


def get_optimal_cpu_threads() -> int:
    """Determine optimal intra_op_num_threads for CPU execution.
    Usually maps to physical cores. Restricted to [1, 8] range.
    """
    count = os.cpu_count() or 4
    return max(1, min(8, count // 2))


def make_session_options(
    *, 
    log_severity_level: int = 3,
    low_mem: bool = False,
    intra_op_num_threads: Optional[int] = None,
    inter_op_num_threads: Optional[int] = None,
) -> Any:
    """Create ONNXRuntime SessionOptions with optional low-memory toggles and threading optimization."""

    so = ort.SessionOptions()
    try:
        so.log_severity_level = int(log_severity_level)
    except Exception:
        pass

    if intra_op_num_threads is not None:
        try:
            so.intra_op_num_threads = int(intra_op_num_threads)
        except Exception:
            pass
    if inter_op_num_threads is not None:
        try:
            so.inter_op_num_threads = int(inter_op_num_threads)
        except Exception:
            pass

    # Default to low-memory mode (reduces peak RSS for large batches).
    if low_mem:
        # These options trade memory for speed; useful for huge batches.
        try:
            so.enable_mem_pattern = False
        except Exception:
            pass
        try:
            so.enable_cpu_mem_arena = False
        except Exception:
            pass

    return so


def make_session(
    model_path: str,
    *,
    providers: list[Any],
    sess_options: Optional[Any] = None,
) -> Any:
    """Create an ONNXRuntime InferenceSession honoring CT_ORT_* toggles."""
    so = sess_options if sess_options is not None else make_session_options()
    return ort.InferenceSession(model_path, sess_options=so, providers=providers)
