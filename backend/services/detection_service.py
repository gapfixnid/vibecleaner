import collections
import hashlib
import json
import logging
import os
import threading
import time
import numpy as np
from typing import List, Optional, Any, Dict
from modules.detection.wrapper import RTDETRv2Detector
from modules.ocr_wrapper import LocalOCR

logger = logging.getLogger(__name__)


class DetectionService:
    _OCR_CACHE_MAX = 8192

    def __init__(
        self,
        detector: Optional[RTDETRv2Detector] = None,
        ocr_engine: Optional[LocalOCR] = None,
    ) -> None:
        self.detector: RTDETRv2Detector = detector or RTDETRv2Detector()
        self.ocr_engine: LocalOCR = ocr_engine or LocalOCR()
        self._ocr_cache: collections.OrderedDict[str, str] = collections.OrderedDict()
        self._lock = threading.RLock()
        self.last_error: str | None = None
        self._ocr_hits: int = 0
        self._ocr_misses: int = 0

        # Load disk cache on startup
        self._load_cache_from_disk()

    # ------------------------------------------------------------------ #
    #  Cache persistence (disk)
    # ------------------------------------------------------------------ #

    def _cache_file_path(self) -> str:
        """Return the path for the persistent OCR cache file."""
        try:
            from modules.config import APP_DATA_DIR
        except ImportError:
            return ""
        return os.path.join(APP_DATA_DIR, "ocr_cache.json")

    def _load_cache_from_disk(self) -> None:
        """Load OCR cache from disk (survives app restart)."""
        path = self._cache_file_path()
        if not path:
            return
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Re-insert in order (most recent first)
                for k, v in reversed(list(data.items())):
                    self._ocr_cache[k] = v
                logger.info("OCR cache loaded: %d entries from disk", len(self._ocr_cache))
        except Exception:
            logger.warning("Failed to load OCR cache from disk", exc_info=True)

    def _save_cache_to_disk(self) -> None:
        """Persist OCR cache to disk. Called after detect completes."""
        path = self._cache_file_path()
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dict(self._ocr_cache), f, ensure_ascii=False)
        except Exception:
            logger.warning("Failed to save OCR cache to disk", exc_info=True)

    # ------------------------------------------------------------------ #
    #  LRU cache helpers
    # ------------------------------------------------------------------ #

    def _get_crop_hash(self, image: np.ndarray, bbox: Any) -> Optional[str]:
        if bbox is None:
            return None
        try:
            h, w = image.shape[:2]
            x1, y1, x2, y2 = map(int, bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                return None
            crop = image[y1:y2, x1:x2]
            return hashlib.md5(crop.tobytes()).hexdigest()
        except Exception:
            logger.exception("Failed to hash OCR crop for bbox=%s", bbox)
            return None

    def _remember_ocr(self, crop_hash: str, text: str) -> None:
        """Store an OCR result using LRU eviction (OrderedDict)."""
        cache = self._ocr_cache
        # If already present, move to end (most recent)
        if crop_hash in cache:
            cache.move_to_end(crop_hash)
        else:
            cache[crop_hash] = text
        # Evict oldest entries if over limit
        while len(cache) > self._OCR_CACHE_MAX:
            cache.popitem(last=False)

    def _cache_hit(self, crop_hash: str) -> str:
        """Retrieve from LRU cache, moving to end (most recent)."""
        self._ocr_cache.move_to_end(crop_hash)
        self._ocr_hits += 1
        return self._ocr_cache[crop_hash]

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def detect_and_ocr(self, image: np.ndarray, lang: str = "Japanese") -> List[Any]:
        """Detect text blocks and run OCR on them, utilizing OCR cache."""
        t0 = time.perf_counter()
        with self._lock:
            # --- Detect ---
            t_detect = time.perf_counter()
            try:
                self.ocr_engine.lang = lang
                blocks = self.detector.detect_bubbles(image)
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("Detection failed. lang=%s", lang)
                raise
            detect_ms = (time.perf_counter() - t_detect) * 1000

            # Check cache for each block
            uncached_blocks = []
            block_hashes = {}
            cached_count = 0
            for block in blocks:
                crop_hash = self._get_crop_hash(image, block.xyxy)
                if crop_hash and crop_hash in self._ocr_cache:
                    block.text = self._cache_hit(crop_hash)
                    cached_count += 1
                else:
                    uncached_blocks.append(block)
                    if crop_hash:
                        block_hashes[block] = crop_hash
            self._ocr_misses += len(uncached_blocks)

            # --- OCR (uncached only) ---
            t_ocr = time.perf_counter()
            if uncached_blocks:
                try:
                    self.ocr_engine.recognize_text(image, uncached_blocks)
                except Exception as exc:
                    self.last_error = str(exc)
                    logger.exception("OCR failed. lang=%s block_count=%s", lang, len(uncached_blocks))
                    raise
                # Store in cache
                for block in uncached_blocks:
                    crop_hash = block_hashes.get(block)
                    if crop_hash:
                        self._remember_ocr(crop_hash, block.text)
            ocr_ms = (time.perf_counter() - t_ocr) * 1000

            total_ms = (time.perf_counter() - t0) * 1000
            logger.debug(
                "detect: %.0fms, ocr: %.0fms, total: %.0fms (bubbles=%d, cached=%d, uncached=%d)",
                detect_ms, ocr_ms, total_ms, len(blocks), cached_count, len(uncached_blocks)
            )

            # Persist cache to disk after each successful detect
            self._save_cache_to_disk()

            self.last_error = None
            return blocks

    def recognize_single_block(self, image: np.ndarray, block: Any, lang: str = "Japanese") -> None:
        """Run OCR on a single block (for manual drag-select), utilizing OCR cache."""
        with self._lock:
            self.ocr_engine.lang = lang
            crop_hash = self._get_crop_hash(image, block.xyxy)
            if crop_hash and crop_hash in self._ocr_cache:
                block.text = self._cache_hit(crop_hash)
                return
            self._ocr_misses += 1

            try:
                self.ocr_engine.recognize_text(image, [block])
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("Single-block OCR failed. lang=%s bbox=%s", lang, getattr(block, "xyxy", None))
                raise
            if crop_hash:
                self._remember_ocr(crop_hash, block.text)

    def get_diagnostics(self) -> dict[str, Any]:
        total = self._ocr_hits + self._ocr_misses
        hit_rate = (self._ocr_hits / total * 100) if total > 0 else 0.0
        detector_available = bool(getattr(self.detector, "available", True))
        detector_error = getattr(self.detector, "engine_error", None)
        return {
            "detector": self.detector.__class__.__name__,
            "detector_available": detector_available,
            "detector_error": detector_error,
            "ocr_engine": self.ocr_engine.__class__.__name__,
            "ocr_cache_entries": len(self._ocr_cache),
            "ocr_cache_max": self._OCR_CACHE_MAX,
            "ocr_cache_hits": self._ocr_hits,
            "ocr_cache_misses": self._ocr_misses,
            "ocr_cache_hit_rate": f"{hit_rate:.1f}%",
            "last_error": self.last_error,
        }
