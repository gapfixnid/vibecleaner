"""Discover the small set of user-supplied ONNX model families we support."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .downloads import ModelDownloader, ModelID, models_base_dir


DEFAULT_DETECTION_MODEL = "High Precision (FP32)"
YOLO_DETECTION_MODEL = "YOLOv8/11 ONNX"
DEFAULT_OCR_MODEL = "ppocr-v6-medium"
SMALL_OCR_MODEL = "ppocr-v6-small"
DEFAULT_INPAINT_MODEL = "aot"
_CUSTOM_PREFIX = "custom:"


@dataclass(frozen=True)
class OnnxModelOption:
    id: str
    label: str
    stage: str
    family: str
    paths: tuple[str, ...]
    config_path: str | None = None


def _root(stage: str) -> Path:
    root = (Path(models_base_dir) / stage).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _custom_id(stage: str, family: str, relative: str) -> str:
    normalized = relative.replace("\\", "/")
    return f"{_CUSTOM_PREFIX}{stage}:{family}:{normalized}"


def _builtin_file_paths() -> set[Path]:
    paths: set[Path] = set()
    for model_id in (
        ModelID.RTDETR_V2_ONNX,
        ModelID.RTDETR_INT8_ONNX,
        ModelID.YOLO_V8_ONNX,
        ModelID.PPOCR_V6_DET_MEDIUM,
        ModelID.PPOCR_V6_REC_MEDIUM,
        ModelID.PPOCR_V6_DET_SMALL,
        ModelID.PPOCR_V6_REC_SMALL,
        ModelID.LAMA_ONNX,
        ModelID.AOT_ONNX,
    ):
        spec = ModelDownloader.registry.get(model_id)
        if spec is None:
            continue
        for filename in spec.files:
            local_name = (spec.save_as or {}).get(filename, filename)
            paths.add((Path(spec.save_dir) / local_name).resolve())
    return paths


def _onnx_files(stage: str) -> list[Path]:
    builtins = _builtin_file_paths()
    root = _root(stage)
    files: list[Path] = []
    for path in root.rglob("*.onnx"):
        if not path.is_file():
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        if resolved not in builtins:
            files.append(resolved)
    return sorted(files)


def _family_from_name(path: Path, families: tuple[str, ...]) -> str | None:
    name = path.as_posix().lower().replace("_", "-")
    if "rt-detr" in name or "rtdetr" in name:
        return "rtdetr" if "rtdetr" in families else None
    return next((family for family in families if family in name), None)


def list_detection_models() -> list[OnnxModelOption]:
    options = [
        OnnxModelOption("High Precision (FP32)", "RT-DETR-v2 FP32", "detection", "rtdetr", ()),
        OnnxModelOption("Small (INT8)", "RT-DETR-v2 INT8", "detection", "rtdetr", ()),
        OnnxModelOption(YOLO_DETECTION_MODEL, "YOLOv8/11 ONNX", "detection", "yolo", ()),
    ]
    root = _root("detection")
    for path in _onnx_files("detection"):
        family = _family_from_name(path.relative_to(root), ("rtdetr", "yolo"))
        if family:
            rel = path.relative_to(root).as_posix()
            options.append(OnnxModelOption(
                _custom_id("detection", family, rel),
                f"{path.stem} ({'RT-DETR-v2' if family == 'rtdetr' else 'YOLOv8/11'})",
                "detection", family, (str(path),),
            ))
    return options


def list_ocr_models() -> list[OnnxModelOption]:
    options = [
        OnnxModelOption(DEFAULT_OCR_MODEL, "PP-OCRv6 Medium ONNX", "ocr", "ppocr", ()),
        OnnxModelOption(SMALL_OCR_MODEL, "PP-OCRv6 Small ONNX", "ocr", "ppocr", ()),
    ]
    root = _root("ocr")
    for directory in sorted({path.parent for path in _onnx_files("ocr")}):
        onnx_files = sorted(directory.glob("*.onnx"))
        det = next((path for path in onnx_files if "det" in path.stem.lower()), None)
        rec = next((path for path in onnx_files if "rec" in path.stem.lower()), None)
        config = next(iter(sorted(directory.glob("*.yml"))), None)
        config = config or next(iter(sorted(directory.glob("*.yaml"))), None)
        if not det or not rec or not config:
            continue
        try:
            config.resolve().relative_to(root)
        except ValueError:
            continue
        rel = directory.relative_to(root).as_posix()
        options.append(OnnxModelOption(
            _custom_id("ocr", "ppocr", rel),
            f"{directory.name} (PP-OCR ONNX)",
            "ocr", "ppocr", (str(det.resolve()), str(rec.resolve())), str(config.resolve()),
        ))
    return options


def list_inpaint_models() -> list[OnnxModelOption]:
    options = [
        OnnxModelOption("aot", "AOT", "inpainting", "aot", ()),
        OnnxModelOption("lama", "LaMa", "inpainting", "lama", ()),
    ]
    root = _root("inpainting")
    for path in _onnx_files("inpainting"):
        family = _family_from_name(path.relative_to(root), ("lama", "aot"))
        if family:
            rel = path.relative_to(root).as_posix()
            options.append(OnnxModelOption(
                _custom_id("inpainting", family, rel),
                f"{path.stem} ({family.upper() if family == 'aot' else 'LaMa'})",
                "inpainting", family, (str(path),),
            ))
    return options


def list_supported_models() -> dict[str, list[OnnxModelOption]]:
    return {
        "detection": list_detection_models(),
        "ocr": list_ocr_models(),
        "inpainting": list_inpaint_models(),
    }


def resolve_model(stage: str, selection: str) -> OnnxModelOption:
    options = list_supported_models().get(stage, [])
    return next((option for option in options if option.id == selection), options[0])
