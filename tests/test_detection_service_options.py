import os
from types import SimpleNamespace
import sqlite3
import tempfile
import threading
import time

import numpy as np

from backend.engines.detection.service import DetectionService

class FakeBlock:
    def __init__(self):
        self.xyxy = [1, 2, 11, 12]
        self.text = ""

class FakeDetector:
    def __init__(self):
        self.calls = []

    def detect_bubbles(
        self,
        image,
        model_name=None,
        confidence_threshold=None,
        tiling_enabled=None,
        bubbles_only=None,
        line_merge_sensitivity=None,
        smart_direction=None,
        text_direction_override=None,
    ):
        self.calls.append(
            {
                "image": image,
                "model_name": model_name,
                "confidence_threshold": confidence_threshold,
                "tiling_enabled": tiling_enabled,
                "bubbles_only": bubbles_only,
                "line_merge_sensitivity": line_merge_sensitivity,
                "smart_direction": smart_direction,
                "text_direction_override": text_direction_override,
            }
        )
        return [FakeBlock()]

class FakeOcr:
    def __init__(self):
        self.lang = None
        self.calls = 0

    def recognize_text(self, image, blocks, engine=None):
        self.calls += 1
        for block in blocks:
            block.text = f"{engine}:text"
        return blocks


class BlockingOcr(FakeOcr):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def recognize_text(self, image, blocks, engine=None):
        self.calls += 1
        self.started.set()
        if not self.release.wait(timeout=2):
            raise TimeoutError("test OCR release timed out")
        for block in blocks:
            block.text = f"{engine}:text"
        return blocks


class CountingDetector(FakeDetector):
    def __init__(self):
        super().__init__()
        self.second_detection_started = threading.Event()

    def detect_bubbles(self, *args, **kwargs):
        blocks = super().detect_bubbles(*args, **kwargs)
        if len(self.calls) >= 2:
            self.second_detection_started.set()
        return blocks

def test_detection_service_passes_explicit_detection_options_from_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        detector = FakeDetector()
        service = DetectionService(
            detector=detector,
            ocr_engine=FakeOcr(),
            config=SimpleNamespace(
                detect_model="Small (INT8)",
                confidence_threshold=0.61,
                tiling_enabled=False,
                bubbles_only=True,
                line_merge_sensitivity=1.9,
                smart_direction=False,
                text_direction_override="vertical",
                ocr_engine="ppocr",
            ),
            cache_file_path=os.path.join(tmpdir, "ocr_cache.sqlite3"),
            cache_flush_interval=60,
        )

        blocks = service.detect_and_ocr(np.zeros((16, 16, 3), dtype=np.uint8), lang="Japanese")

        assert detector.calls[0]["model_name"] == "Small (INT8)"
        assert detector.calls[0]["confidence_threshold"] == 0.61
        assert detector.calls[0]["tiling_enabled"] is False
        assert detector.calls[0]["bubbles_only"] is True
        assert detector.calls[0]["line_merge_sensitivity"] == 1.9
        assert detector.calls[0]["smart_direction"] is False
        assert detector.calls[0]["text_direction_override"] == "vertical"
        assert blocks[0].text == "ppocr:text"
        service.shutdown()


def test_detection_and_ocr_can_run_as_independent_operations():
    with tempfile.TemporaryDirectory() as tmpdir:
        detector = FakeDetector()
        ocr = FakeOcr()
        service = DetectionService(
            detector=detector,
            ocr_engine=ocr,
            config=SimpleNamespace(
                detect_model="Small (INT8)", confidence_threshold=0.5,
                tiling_enabled=False, bubbles_only=False, line_merge_sensitivity=1.2,
                smart_direction=True, text_direction_override="auto", ocr_engine="ppocr",
            ),
            cache_file_path=os.path.join(tmpdir, "ocr_cache.sqlite3"),
            cache_flush_interval=60,
        )
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        blocks = service.detect_only(image)
        assert ocr.calls == 0
        service.ocr_only(image, blocks, lang="Japanese")
        assert ocr.calls == 1
        assert blocks[0].text == "ppocr:text"
        service.shutdown()


def test_cached_single_block_ocr_does_not_wait_for_another_ocr_inference():
    with tempfile.TemporaryDirectory() as tmpdir:
        ocr = BlockingOcr()
        service = DetectionService(
            detector=FakeDetector(),
            ocr_engine=ocr,
            config=SimpleNamespace(ocr_engine="ppocr"),
            cache_file_path=os.path.join(tmpdir, "ocr_cache.sqlite3"),
            cache_flush_interval=60,
        )
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        uncached = FakeBlock()
        cached = FakeBlock()
        cached.xyxy = [2, 2, 12, 14]
        crop_hash = service._get_crop_hash(image, cached.xyxy)
        assert crop_hash is not None
        service._remember_ocr(crop_hash, "cached text")

        worker = threading.Thread(target=service.recognize_single_block, args=(image, uncached))
        worker.start()
        assert ocr.started.wait(timeout=1)

        service.recognize_single_block(image, cached)

        assert cached.text == "cached text"
        assert worker.is_alive()
        ocr.release.set()
        worker.join(timeout=1)
        assert not worker.is_alive()
        service.shutdown()


def test_second_page_detection_starts_while_first_page_ocr_is_running():
    with tempfile.TemporaryDirectory() as tmpdir:
        detector = CountingDetector()
        ocr = BlockingOcr()
        service = DetectionService(
            detector=detector,
            ocr_engine=ocr,
            config=SimpleNamespace(
                detect_model="Small (INT8)",
                confidence_threshold=0.5,
                tiling_enabled=False,
                bubbles_only=False,
                line_merge_sensitivity=1.2,
                smart_direction=True,
                text_direction_override="auto",
                ocr_engine="ppocr",
            ),
            cache_file_path=os.path.join(tmpdir, "ocr_cache.sqlite3"),
            cache_flush_interval=60,
        )
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        first = threading.Thread(target=service.detect_and_ocr, args=(image,))
        first.start()
        assert ocr.started.wait(timeout=1)

        second = threading.Thread(target=service.detect_and_ocr, args=(image,))
        second.start()
        assert detector.second_detection_started.wait(timeout=1)

        ocr.release.set()
        first.join(timeout=1)
        second.join(timeout=1)
        assert not first.is_alive()
        assert not second.is_alive()
        service.shutdown()


def test_ocr_cache_flushes_dirty_entries_to_sqlite_without_immediate_disk_dump():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "ocr_cache.sqlite3")
        ocr = FakeOcr()
        service = DetectionService(
            detector=FakeDetector(),
            ocr_engine=ocr,
            config=SimpleNamespace(ocr_engine="ppocr"),
            cache_file_path=cache_path,
            cache_flush_interval=60,
        )
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        block = FakeBlock()

        service.recognize_single_block(image, block)

        assert not os.path.exists(cache_path)
        service.flush_ocr_cache()

        connection = sqlite3.connect(cache_path)
        try:
            row = connection.execute("SELECT text FROM ocr_cache").fetchone()
        finally:
            connection.close()
        assert row == ("ppocr:text",)

        restored_ocr = FakeOcr()
        restored = DetectionService(
            detector=FakeDetector(),
            ocr_engine=restored_ocr,
            config=SimpleNamespace(ocr_engine="ppocr"),
            cache_file_path=cache_path,
            cache_flush_interval=60,
        )
        cached = FakeBlock()

        restored.recognize_single_block(image, cached)

        assert cached.text == "ppocr:text"
        assert restored_ocr.calls == 0
        service.shutdown()
        restored.shutdown()


def test_ocr_cache_flushes_after_the_debounce_interval():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "ocr_cache.sqlite3")
        service = DetectionService(
            detector=FakeDetector(),
            ocr_engine=FakeOcr(),
            config=SimpleNamespace(ocr_engine="ppocr"),
            cache_file_path=cache_path,
            cache_flush_interval=0.01,
        )

        service.recognize_single_block(np.zeros((16, 16, 3), dtype=np.uint8), FakeBlock())

        deadline = time.monotonic() + 1
        while not os.path.exists(cache_path) and time.monotonic() < deadline:
            time.sleep(0.01)

        assert os.path.exists(cache_path)
        service.shutdown()
