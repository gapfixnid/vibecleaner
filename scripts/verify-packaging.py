#!/usr/bin/env python3
"""Validate release packaging prerequisites without downloading large assets."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
TAURI_ROOT = REPO_ROOT / "desktop" / "src-tauri"
TAURI_CONFIG = TAURI_ROOT / "tauri.conf.json"
SIDECAR_RESOURCE = "binaries/server-x86_64-pc-windows-msvc.exe"
SIDECAR_PATH = TAURI_ROOT / SIDECAR_RESOURCE
BUNDLED_FONT = BACKEND_ROOT / "app" / "assets" / "fonts" / "PretendardVariable.ttf"
BUNDLED_FONT_LICENSE = BACKEND_ROOT / "app" / "assets" / "fonts" / "LICENSE-Pretendard.txt"
RUNTIME_REQUIREMENTS = REPO_ROOT / "requirements-runtime.txt"
FORBIDDEN_RUNTIME_REQUIREMENTS = {
    "torch",
    "torchvision",
    "torchmetrics",
    "pytorch-lightning",
    "pytorch_lightning",
}


def _add_backend_to_path() -> None:
    backend = str(BACKEND_ROOT)
    repo = str(REPO_ROOT)
    for path in (repo, backend):
        if path not in sys.path:
            sys.path.insert(0, path)


def _load_tauri_config() -> dict:
    with TAURI_CONFIG.open("r", encoding="utf-8") as f:
        return json.load(f)


def _check_file(path: Path, label: str, errors: list[str], *, min_size: int = 1) -> None:
    if not path.exists():
        errors.append(f"missing {label}: {path}")
        return
    if path.is_file() and path.stat().st_size < min_size:
        errors.append(f"{label} is unexpectedly small: {path} ({path.stat().st_size} bytes)")


def _check_tauri_resources(config: dict, errors: list[str]) -> None:
    resources = config.get("bundle", {}).get("resources", [])
    if SIDECAR_RESOURCE not in resources:
        errors.append(f"tauri.conf.json bundle.resources must include {SIDECAR_RESOURCE!r}")
    _check_file(SIDECAR_PATH, "backend sidecar", errors, min_size=1_000_000)


def _check_fonts(errors: list[str]) -> None:
    _check_file(BUNDLED_FONT, "bundled Pretendard font", errors, min_size=100_000)
    _check_file(BUNDLED_FONT_LICENSE, "Pretendard font license", errors)


def _check_runtime_requirements(errors: list[str]) -> None:
    _check_file(RUNTIME_REQUIREMENTS, "runtime requirements", errors)
    if not RUNTIME_REQUIREMENTS.exists():
        return

    for raw_line in RUNTIME_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        package_name = line.split(";", 1)[0].split("[", 1)[0]
        for marker in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            package_name = package_name.split(marker, 1)[0]
        package_name = package_name.strip().lower().replace("_", "-")
        if package_name in FORBIDDEN_RUNTIME_REQUIREMENTS:
            errors.append(f"runtime requirements must not include optional Torch package: {raw_line}")


def _model_ids(profile: str):
    _add_backend_to_path()
    from download_models import get_model_ids

    return get_model_ids(profile)


def _check_model_registry(profile: str, errors: list[str]) -> None:
    _add_backend_to_path()
    from infrastructure.downloads import ModelDownloader

    for model_id in _model_ids(profile):
        spec = ModelDownloader.registry.get(model_id)
        if spec is None:
            errors.append(f"model profile {profile!r} references unregistered model: {model_id}")
            continue
        if not spec.files:
            errors.append(f"model {model_id.value} has no declared files")
        if len(spec.files) != len(spec.sha256):
            errors.append(
                f"model {model_id.value} files/checksum length mismatch "
                f"({len(spec.files)} files, {len(spec.sha256)} checksums)"
            )
        if not spec.save_dir:
            errors.append(f"model {model_id.value} has no save_dir")
        if not spec.url and not spec.additional_urls:
            errors.append(f"model {model_id.value} has no download URL")


def _check_model_files(profile: str, errors: list[str]) -> None:
    _add_backend_to_path()
    from infrastructure.downloads import ModelDownloader

    for model_id in _model_ids(profile):
        if not ModelDownloader.is_downloaded(model_id):
            download_cmd = (
                r".\venv\Scripts\python.exe download_models.py --minimal"
                if profile == "minimal"
                else r".\venv\Scripts\python.exe download_models.py"
            )
            errors.append(
                f"model not downloaded or checksum mismatch: {model_id.value}; "
                f"run `{download_cmd}` first"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("minimal", "all"),
        default="all",
        help="Model profile to validate. Defaults to all.",
    )
    parser.add_argument(
        "--require-model-files",
        action="store_true",
        help="Also require every model file in the selected profile to exist locally.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    config = _load_tauri_config()
    _check_tauri_resources(config, errors)
    _check_fonts(errors)
    _check_runtime_requirements(errors)
    _check_model_registry(args.profile, errors)
    if args.require_model_files:
        _check_model_files(args.profile, errors)

    if errors:
        print("Packaging verification failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(f"Packaging verification passed (profile={args.profile}, require_model_files={args.require_model_files}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
