import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.models import MangaPage
from infrastructure.image.loading import ensure_original_thumbnail, ensure_page_image


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


if __name__ == "__main__":
    unittest.main()
