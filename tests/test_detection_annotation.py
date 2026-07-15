from __future__ import annotations

from scripts.annotate_detection_corpus import image_files, normalize_box


def test_normalize_box_orders_coordinates_and_rejects_tiny_drags():
    assert normalize_box((20.4, 30.4), (5.2, 10.6)) == [5, 11, 20, 30]
    assert normalize_box((5, 5), (6, 8)) is None


def test_image_files_returns_supported_images_in_order(tmp_path):
    (tmp_path / "b.jpg").write_bytes(b"")
    (tmp_path / "a.PNG").write_bytes(b"")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")

    assert image_files(tmp_path) == [tmp_path / "a.PNG", tmp_path / "b.jpg"]
