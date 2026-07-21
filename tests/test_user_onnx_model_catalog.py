from pathlib import Path

from backend.infrastructure import model_catalog


def test_discovers_only_supported_named_onnx_families(tmp_path, monkeypatch):
    monkeypatch.setattr(model_catalog, "models_base_dir", str(tmp_path))
    detection = tmp_path / "detection"
    inpainting = tmp_path / "inpainting"
    detection.mkdir()
    inpainting.mkdir()
    (detection / "rtdetr-comic.onnx").write_bytes(b"")
    (detection / "yolov11-bubbles.onnx").write_bytes(b"")
    (detection / "unknown.onnx").write_bytes(b"")
    (inpainting / "lama-custom.onnx").write_bytes(b"")
    (inpainting / "aot-custom.onnx").write_bytes(b"")
    (inpainting / "migan.onnx").write_bytes(b"")

    detection_options = model_catalog.list_detection_models()
    inpaint_options = model_catalog.list_inpaint_models()

    assert [option.family for option in detection_options] == ["rtdetr", "rtdetr", "yolo", "rtdetr", "yolo"]
    assert [option.family for option in inpaint_options] == ["aot", "lama", "aot", "lama"]
    assert not any("unknown" in option.id for option in detection_options)
    assert not any("migan" in option.id for option in inpaint_options)


def test_discovers_ppocr_only_as_det_rec_config_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(model_catalog, "models_base_dir", str(tmp_path))
    valid = tmp_path / "ocr" / "my-ppocr"
    invalid = tmp_path / "ocr" / "missing-config"
    valid.mkdir(parents=True)
    invalid.mkdir(parents=True)
    (valid / "text_det.onnx").write_bytes(b"")
    (valid / "text_rec.onnx").write_bytes(b"")
    (valid / "inference.yml").write_text("PostProcess: {}", encoding="utf-8")
    (invalid / "text_det.onnx").write_bytes(b"")
    (invalid / "text_rec.onnx").write_bytes(b"")

    options = model_catalog.list_ocr_models()

    assert len(options) == 3
    assert options[0].id == model_catalog.DEFAULT_OCR_MODEL
    assert options[1].id == model_catalog.SMALL_OCR_MODEL
    assert options[2].family == "ppocr"
    assert options[2].id.endswith("my-ppocr")
