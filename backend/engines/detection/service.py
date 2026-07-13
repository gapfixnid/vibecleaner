import atexit
import collections
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
import numpy as np
from typing import List, Optional, Any, Dict
from ...core.config import config_value
from ...core.providers.concurrency import ProviderConcurrencyGate
from .wrapper import RTDETRv2Detector
from ..ocr.local import LocalOCR

logger = logging.getLogger(__name__)


class DetectionService:
    _OCR_CACHE_MAX = 8192

    def __init__(
        self,
        detector: Optional[RTDETRv2Detector] = None,
        ocr_engine: Optional[LocalOCR] = None,
        config: Any = None,
        cache_file_path: str | None = None,
        cache_flush_interval: float = 2.0,
    ) -> None:
        self.detector: RTDETRv2Detector = detector or RTDETRv2Detector()
        self.ocr_engine: LocalOCR = ocr_engine or LocalOCR()
        self.config = config
        self._ocr_cache: collections.OrderedDict[str, str] = collections.OrderedDict()
        self._detector_lock = threading.RLock()
        self._ocr_engine_lock = threading.RLock()
        self._cache_lock = threading.RLock()
        self._cache_flush_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._detection_gate = ProviderConcurrencyGate(max_concurrency=1, queue_capacity=2)
        self._ocr_gate = ProviderConcurrencyGate(max_concurrency=1, queue_capacity=4)
        self._cache_file_path_override = cache_file_path
        self._cache_flush_interval = max(0.0, float(cache_flush_interval))
        self._cache_flush_timer: threading.Timer | None = None
        self._cache_dirty = False
        self._cache_revision = 0
        self._pending_cache_upserts: dict[str, str] = {}
        self._pending_cache_deletes: set[str] = set()
        self._legacy_cache_path_to_remove: str | None = None
        self.last_error: str | None = None
        self._ocr_hits: int = 0
        self._ocr_misses: int = 0

        atexit.register(self.flush_ocr_cache)
        self._load_cache_from_disk()

    def configure_queues(
        self,
        *,
        detection: tuple[int, int],
        ocr: tuple[int, int],
    ) -> None:
        self._detection_gate = ProviderConcurrencyGate(
            max_concurrency=detection[0], queue_capacity=detection[1]
        )
        self._ocr_gate = ProviderConcurrencyGate(
            max_concurrency=ocr[0], queue_capacity=ocr[1]
        )

    def _ocr_engine_name(self, engine: str | None = None) -> str:
        return engine or config_value(self.config, "ocr_engine")

    def _detect_model_name(self, model_name: str | None = None) -> str:
        return model_name or config_value(self.config, "detect_model")

    def _confidence_threshold(self, confidence_threshold: float | None = None) -> float:
        if confidence_threshold is not None:
            return float(confidence_threshold)
        return float(config_value(self.config, "confidence_threshold"))

    def _tiling_enabled(self, tiling_enabled: bool | None = None) -> bool:
        if tiling_enabled is not None:
            return bool(tiling_enabled)
        return bool(config_value(self.config, "tiling_enabled"))

    def _bubbles_only(self, bubbles_only: bool | None = None) -> bool:
        if bubbles_only is not None:
            return bool(bubbles_only)
        return bool(config_value(self.config, "bubbles_only"))

    def _line_merge_sensitivity(self, line_merge_sensitivity: float | None = None) -> float:
        if line_merge_sensitivity is not None:
            return float(line_merge_sensitivity)
        return float(config_value(self.config, "line_merge_sensitivity"))

    def _smart_direction(self, smart_direction: bool | None = None) -> bool:
        if smart_direction is not None:
            return bool(smart_direction)
        return bool(config_value(self.config, "smart_direction"))

    def _text_direction_override(self, text_direction_override: str | None = None) -> str:
        return str(text_direction_override or config_value(self.config, "text_direction_override") or "auto")

    # ------------------------------------------------------------------ #
    #  Cache persistence (disk)
    # ------------------------------------------------------------------ #

    def _cache_file_path(self) -> str:
        """Return the path for the persistent OCR cache database."""
        if self._cache_file_path_override:
            return self._cache_file_path_override
        from ...infrastructure.storage import get_app_data_dir

        return os.path.join(get_app_data_dir(), "ocr_cache.sqlite3")

    def _legacy_cache_file_path(self) -> str | None:
        if self._cache_file_path_override:
            return None
        from ...infrastructure.storage import get_app_data_dir

        return os.path.join(get_app_data_dir(), "ocr_cache.json")

    def _load_cache_from_disk(self) -> None:
        """Load OCR cache from SQLite, migrating the legacy JSON file once."""
        path = self._cache_file_path()
        try:
            if os.path.exists(path):
                connection = sqlite3.connect(path)
                try:
                    self._ensure_cache_schema(connection)
                    rows = connection.execute(
                        "SELECT crop_hash, text FROM ocr_cache ORDER BY updated_at ASC LIMIT ?",
                        (self._OCR_CACHE_MAX,),
                    ).fetchall()
                finally:
                    connection.close()
                with self._cache_lock:
                    for crop_hash, text in rows:
                        self._ocr_cache[str(crop_hash)] = str(text)
                logger.info("OCR cache loaded: %d entries from SQLite", len(rows))
                return

            legacy_path = self._legacy_cache_file_path()
            if not legacy_path or not os.path.exists(legacy_path):
                return
            with open(legacy_path, "r", encoding="utf-8") as cache_file:
                legacy_data = json.load(cache_file)
            if not isinstance(legacy_data, dict):
                return
            with self._cache_lock:
                for crop_hash, text in reversed(list(legacy_data.items())):
                    self._ocr_cache[str(crop_hash)] = str(text)
                while len(self._ocr_cache) > self._OCR_CACHE_MAX:
                    self._ocr_cache.popitem(last=False)
                self._pending_cache_upserts.update(self._ocr_cache)
                self._cache_dirty = bool(self._ocr_cache)
                self._cache_revision += 1
                if self._cache_dirty:
                    self._legacy_cache_path_to_remove = legacy_path
                    self._schedule_cache_flush_locked()
            logger.info("OCR cache migration queued: %d entries from JSON", len(self._ocr_cache))
        except Exception:
            logger.warning("Failed to load OCR cache from disk", exc_info=True)

    @staticmethod
    def _ensure_cache_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ocr_cache (
                crop_hash TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )

    def _schedule_cache_flush_locked(self) -> None:
        if not self._cache_dirty:
            return
        if self._cache_flush_timer and self._cache_flush_timer.is_alive():
            return
        timer = threading.Timer(self._cache_flush_interval, self.flush_ocr_cache)
        timer.daemon = True
        self._cache_flush_timer = timer
        timer.start()

    def flush_ocr_cache(self) -> None:
        """Persist pending OCR cache changes in one short SQLite transaction."""
        with self._cache_flush_lock:
            with self._cache_lock:
                self._cache_flush_timer = None
                if not self._cache_dirty:
                    return
                upserts = dict(self._pending_cache_upserts)
                deletes = set(self._pending_cache_deletes)
                revision = self._cache_revision
                legacy_path = self._legacy_cache_path_to_remove

            try:
                path = self._cache_file_path()
                cache_directory = os.path.dirname(path)
                if cache_directory:
                    os.makedirs(cache_directory, exist_ok=True)
                timestamp = time.time_ns()
                connection = sqlite3.connect(path)
                try:
                    self._ensure_cache_schema(connection)
                    with connection:
                        if deletes:
                            connection.executemany(
                                "DELETE FROM ocr_cache WHERE crop_hash = ?",
                                [(crop_hash,) for crop_hash in deletes],
                            )
                        if upserts:
                            connection.executemany(
                                """
                                INSERT INTO ocr_cache (crop_hash, text, updated_at)
                                VALUES (?, ?, ?)
                                ON CONFLICT(crop_hash) DO UPDATE SET
                                    text = excluded.text,
                                    updated_at = excluded.updated_at
                                """,
                                [
                                    (crop_hash, text, timestamp + index)
                                    for index, (crop_hash, text) in enumerate(upserts.items())
                                ],
                            )
                        connection.execute(
                            """
                            DELETE FROM ocr_cache
                            WHERE crop_hash IN (
                                SELECT crop_hash FROM ocr_cache
                                ORDER BY updated_at DESC, rowid DESC
                                LIMIT -1 OFFSET ?
                            )
                            """,
                            (self._OCR_CACHE_MAX,),
                        )
                finally:
                    connection.close()
            except Exception:
                logger.warning("Failed to flush OCR cache to SQLite", exc_info=True)
                with self._cache_lock:
                    self._schedule_cache_flush_locked()
                return

            with self._cache_lock:
                if revision == self._cache_revision:
                    self._pending_cache_upserts.clear()
                    self._pending_cache_deletes.clear()
                    self._cache_dirty = False
                else:
                    for crop_hash, text in upserts.items():
                        if self._pending_cache_upserts.get(crop_hash) == text:
                            self._pending_cache_upserts.pop(crop_hash, None)
                    self._pending_cache_deletes.difference_update(deletes)
                    self._cache_dirty = bool(self._pending_cache_upserts or self._pending_cache_deletes)
                    self._schedule_cache_flush_locked()
                if legacy_path and self._legacy_cache_path_to_remove == legacy_path:
                    self._legacy_cache_path_to_remove = None

            if legacy_path:
                try:
                    if os.path.exists(legacy_path):
                        os.remove(legacy_path)
                except OSError:
                    logger.warning("Failed to remove migrated OCR JSON cache: %s", legacy_path)

    def shutdown(self) -> None:
        """Cancel deferred work and flush pending cache writes before shutdown."""
        with self._cache_lock:
            timer = self._cache_flush_timer
            self._cache_flush_timer = None
        if timer:
            timer.cancel()
        self.flush_ocr_cache()

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
        with self._cache_lock:
            cache = self._ocr_cache
            if crop_hash in cache:
                cache.move_to_end(crop_hash)
            else:
                cache[crop_hash] = text
            self._pending_cache_upserts[crop_hash] = text
            self._pending_cache_deletes.discard(crop_hash)
            while len(cache) > self._OCR_CACHE_MAX:
                evicted_hash, _ = cache.popitem(last=False)
                self._pending_cache_upserts.pop(evicted_hash, None)
                self._pending_cache_deletes.add(evicted_hash)
            self._cache_dirty = True
            self._cache_revision += 1
            self._schedule_cache_flush_locked()

    def _get_cached_ocr(self, crop_hash: str | None) -> str | None:
        if not crop_hash:
            return None
        with self._cache_lock:
            text = self._ocr_cache.get(crop_hash)
            if text is None:
                return None
            self._ocr_cache.move_to_end(crop_hash)
            self._ocr_hits += 1
            return text

    def _record_ocr_misses(self, count: int) -> None:
        if count <= 0:
            return
        with self._cache_lock:
            self._ocr_misses += count

    def _set_last_error(self, value: str | None) -> None:
        with self._state_lock:
            self.last_error = value

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def detect_only(
        self,
        image: np.ndarray,
        *,
        model_name: str | None = None,
        confidence_threshold: float | None = None,
        tiling_enabled: bool | None = None,
        bubbles_only: bool | None = None,
        line_merge_sensitivity: float | None = None,
        smart_direction: bool | None = None,
        text_direction_override: str | None = None,
    ) -> List[Any]:
        """Detect text blocks without running OCR."""
        try:
            with self._detection_gate.slot():
                with self._detector_lock:
                    blocks = self.detector.detect_bubbles(
                    image,
                    model_name=self._detect_model_name(model_name),
                    confidence_threshold=self._confidence_threshold(confidence_threshold),
                    tiling_enabled=self._tiling_enabled(tiling_enabled),
                    bubbles_only=self._bubbles_only(bubbles_only),
                    line_merge_sensitivity=self._line_merge_sensitivity(line_merge_sensitivity),
                    smart_direction=self._smart_direction(smart_direction),
                    text_direction_override=self._text_direction_override(text_direction_override),
                )
        except Exception as exc:
            self._set_last_error(str(exc))
            logger.exception("Detection failed")
            raise
        self._set_last_error(None)
        return blocks

    def ocr_only(
        self,
        image: np.ndarray,
        blocks: List[Any],
        *,
        lang: str = "Japanese",
        engine: str | None = None,
    ) -> List[Any]:
        """Run OCR for previously detected blocks, preserving the legacy cache."""
        uncached_blocks = []
        block_hashes = {}
        for block in blocks:
            crop_hash = self._get_crop_hash(image, block.xyxy)
            cached_text = self._get_cached_ocr(crop_hash)
            if cached_text is not None:
                block.text = cached_text
            else:
                uncached_blocks.append(block)
                if crop_hash:
                    block_hashes[block] = crop_hash
        self._record_ocr_misses(len(uncached_blocks))
        if uncached_blocks:
            try:
                with self._ocr_gate.slot():
                    with self._ocr_engine_lock:
                        self.ocr_engine.lang = lang
                        self.ocr_engine.recognize_text(
                            image, uncached_blocks, engine=self._ocr_engine_name(engine)
                        )
            except Exception as exc:
                self._set_last_error(str(exc))
                logger.exception("OCR failed. lang=%s block_count=%s", lang, len(uncached_blocks))
                raise
            for block in uncached_blocks:
                crop_hash = block_hashes.get(block)
                if crop_hash:
                    self._remember_ocr(crop_hash, block.text)
        self._set_last_error(None)
        return blocks

    def detect_and_ocr(
        self,
        image: np.ndarray,
        lang: str = "Japanese",
        engine: str | None = None,
        model_name: str | None = None,
        confidence_threshold: float | None = None,
        tiling_enabled: bool | None = None,
        bubbles_only: bool | None = None,
        line_merge_sensitivity: float | None = None,
        smart_direction: bool | None = None,
        text_direction_override: str | None = None,
    ) -> List[Any]:
        """Detect text blocks and run OCR on them, utilizing OCR cache."""
        t0 = time.perf_counter()
        t_detect = time.perf_counter()
        blocks = self.detect_only(
            image,
            model_name=model_name,
            confidence_threshold=confidence_threshold,
            tiling_enabled=tiling_enabled,
            bubbles_only=bubbles_only,
            line_merge_sensitivity=line_merge_sensitivity,
            smart_direction=smart_direction,
            text_direction_override=text_direction_override,
        )
        detect_ms = (time.perf_counter() - t_detect) * 1000
        t_ocr = time.perf_counter()
        self.ocr_only(image, blocks, lang=lang, engine=engine)
        ocr_ms = (time.perf_counter() - t_ocr) * 1000

        total_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "detect: %.0fms, ocr: %.0fms, total: %.0fms (bubbles=%d, cache_hits=%d, cache_misses=%d)",
            detect_ms, ocr_ms, total_ms, len(blocks), self._ocr_hits, self._ocr_misses
        )

        self._set_last_error(None)
        return blocks

    def recognize_single_block(
        self,
        image: np.ndarray,
        block: Any,
        lang: str = "Japanese",
        engine: str | None = None,
    ) -> None:
        """Run OCR on a single block without blocking cache hits on model inference."""
        crop_hash = self._get_crop_hash(image, block.xyxy)
        cached_text = self._get_cached_ocr(crop_hash)
        if cached_text is not None:
            block.text = cached_text
            return
        self._record_ocr_misses(1)

        try:
            with self._ocr_gate.slot():
                with self._ocr_engine_lock:
                    self.ocr_engine.lang = lang
                    self.ocr_engine.recognize_text(image, [block], engine=self._ocr_engine_name(engine))
        except Exception as exc:
            self._set_last_error(str(exc))
            logger.exception("Single-block OCR failed. lang=%s bbox=%s", lang, getattr(block, "xyxy", None))
            raise
        if crop_hash:
            self._remember_ocr(crop_hash, block.text)
        self._set_last_error(None)

    def recognize_region(
        self,
        image: np.ndarray,
        xyxy: List[float],
        lang: str = "Japanese",
        engine: str | None = None,
    ) -> str:
        """Run OCR on an image region given as [x1, y1, x2, y2].

        Engine-domain wrapper so API callers do not need the TextBlock type.
        """
        from ..common.textblock import TextBlock

        block = TextBlock(text_bbox=np.array(xyxy, dtype=np.int32))
        self.recognize_single_block(image, block, lang=lang, engine=engine)
        return block.text

    def get_diagnostics(self) -> dict[str, Any]:
        with self._cache_lock:
            total = self._ocr_hits + self._ocr_misses
            cache_entries = len(self._ocr_cache)
            cache_hits = self._ocr_hits
            cache_misses = self._ocr_misses
            cache_dirty = self._cache_dirty
        hit_rate = (cache_hits / total * 100) if total > 0 else 0.0
        detector_available = bool(getattr(self.detector, "available", True))
        detector_error = getattr(self.detector, "engine_error", None)
        with self._state_lock:
            last_error = self.last_error
        return {
            "detector": self.detector.__class__.__name__,
            "detector_available": detector_available,
            "detector_error": detector_error,
            "ocr_engine": self.ocr_engine.__class__.__name__,
            "ocr_cache_entries": cache_entries,
            "ocr_cache_max": self._OCR_CACHE_MAX,
            "ocr_cache_hits": cache_hits,
            "ocr_cache_misses": cache_misses,
            "ocr_cache_hit_rate": f"{hit_rate:.1f}%",
            "ocr_cache_dirty": cache_dirty,
            "detection_queue": self._detection_gate.status(),
            "ocr_queue": self._ocr_gate.status(),
            "last_error": last_error,
        }
