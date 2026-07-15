from __future__ import annotations

import os
import logging
import site
from typing import Any
import onnxruntime as ort

logger = logging.getLogger(__name__)
_DLL_DIRECTORY_HANDLES: list[Any] = []


def _register_nvidia_dll_directories() -> None:
    """Register pip-installed CUDA/cuDNN DLL directories before ORT loads."""
    if os.name != "nt":
        return
    site_packages = []
    try:
        site_packages.extend(site.getsitepackages())
    except AttributeError:
        pass
    try:
        site_packages.append(site.getusersitepackages())
    except AttributeError:
        pass
    names = (
        ("cudnn", "bin"),
        ("cuda_runtime", "bin"),
        ("cublas", "bin"),
        ("cufft", "bin"),
        ("curand", "bin"),
        ("nvjitlink", "bin"),
        ("cuda_nvrtc", "bin"),
    )
    for root in site_packages:
        for package, subdirectory in names:
            directory = os.path.join(root, "nvidia", package, subdirectory)
            if not os.path.isdir(directory):
                continue
            os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
            add_dll_directory = getattr(os, "add_dll_directory", None)
            if callable(add_dll_directory):
                try:
                    _DLL_DIRECTORY_HANDLES.append(add_dll_directory(directory))
                except OSError:
                    logger.debug("Could not register NVIDIA DLL directory: %s", directory)


def _preload_onnxruntime_dlls() -> None:
    """Load CUDA/cuDNN DLLs installed as NVIDIA Python packages on Windows."""
    _register_nvidia_dll_directories()
    preload = getattr(ort, "preload_dlls", None)
    if not callable(preload):
        return
    try:
        # An empty directory asks ORT to search the NVIDIA site-packages
        # runtime packages installed by onnxruntime-gpu[cuda,cudnn].
        preload(directory="")
    except Exception:
        logger.debug("Could not preload ONNX Runtime GPU DLLs", exc_info=True)


_preload_onnxruntime_dlls()


def resolve_device(use_gpu: bool, backend: str = "onnx") -> str:
    """Resolve the supported ONNX device; CUDA falls back to CPU."""
    if not use_gpu:
        return "cpu"
    return _resolve_onnx_device()


def _resolve_onnx_device() -> str:
    """Resolve the best available ONNX device."""
    providers = ort.get_available_providers() 

    if not providers:
        return "cpu"

    if "CUDAExecutionProvider" in providers:
        return "cuda"
    
    return "cpu"

def get_providers(device: str | None = None) -> list[str]:
    """Return the supported ONNX Runtime providers for the requested device.

    Rules:
    - If device is the string 'cpu' (case-insensitive) -> return ['CPUExecutionProvider']
    - CUDA requests return CUDA followed by CPU fallback when available
    - If no providers are available, fall back to ['CPUExecutionProvider']
    """
    try:
        available = ort.get_available_providers()
    except Exception:
        available = []

    if device and isinstance(device, str) and device.lower() == 'cpu':
        return ['CPUExecutionProvider']

    available = [provider for provider in available if provider in {
        "CUDAExecutionProvider", "CPUExecutionProvider"
    }]
    if not available:
        return ['CPUExecutionProvider']

    if isinstance(device, str) and device.lower() == "cuda":
        return available
    return ["CPUExecutionProvider"]


def is_gpu_available() -> bool:
    """Return whether CUDA is available to ONNX Runtime."""
    try:
        providers = ort.get_available_providers()
    except Exception:
        providers = []

    return "CUDAExecutionProvider" in providers
