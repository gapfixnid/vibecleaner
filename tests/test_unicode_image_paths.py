import os
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from backend.core.models import MangaPage
from backend.infrastructure.image.loading import ensure_original_thumbnail, ensure_page_image
import backend.infrastructure.image.loading as image_loading

class UnicodeImagePathTests(unittest.TestCase):
    def _write_unicode_png(self) -> Path:
        tmp_dir = Path(tempfile.mkdtemp(prefix="vibecleaner_テスト_"))
        image_path = tmp_dir / "画像_日本語.png"
        image = np.zeros((16, 20, 3), dtype=np.uint8)
        image[:, :, 0] = 255
        ok, encoded = cv2.imencode(".png", image)
        self.assertTrue(ok)
        encoded.tofile(str(image_path))
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
        return image_path

    def test_ensure_page_image_loads_unicode_path(self):
        image_path = self._write_unicode_png()
        page = MangaPage(file_path=str(image_path), cv_image=np.array([]))
        page._loaded = False

        ensure_page_image(page)

        self.assertEqual(page.cv_image.shape[:2], (16, 20))
        self.assertTrue(page._loaded)

    def test_ensure_original_thumbnail_loads_unicode_path(self):
        image_path = self._write_unicode_png()
        page = MangaPage(file_path=str(image_path), cv_image=np.array([]))
        page._loaded = False

        thumbnail = ensure_original_thumbnail(page)

        self.assertGreater(len(thumbnail), 0)
        self.assertEqual(thumbnail[:8], b"\x89PNG\r\n\x1a\n")

    def test_concurrent_thumbnail_requests_generate_once(self):
        page = MangaPage(file_path="sample.png", cv_image=None)
        page._loaded = False
        image = np.zeros((32, 32, 3), dtype=np.uint8)

        with (
            patch.object(image_loading, "load_cv_image", return_value=image) as load_image,
            patch.object(image_loading, "encode_thumbnail_bytes", return_value=b"thumbnail") as encode,
            ThreadPoolExecutor(max_workers=4) as executor,
        ):
            results = list(executor.map(lambda _: ensure_original_thumbnail(page), range(4)))

        self.assertEqual(results, [b"thumbnail"] * 4)
        load_image.assert_called_once_with("sample.png")
        encode.assert_called_once_with(image)

if __name__ == "__main__":
    unittest.main()
