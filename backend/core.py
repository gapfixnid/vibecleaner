import os
import sys
import cv2
import logging
import time
import uuid
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from typing import Any, Callable, List
from fastapi import HTTPException
from PySide6.QtWidgets import QApplication

# Ensure backend/ is in python path so imports like services.*, app.models, modules.* resolve correctly
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Setup offscreen Qt application so QFont/QFontMetrics work headlessly
qt_app = QApplication.instance()
if qt_app is None:
    qt_app = QApplication(["-platform", "offscreen"])

from services.translation_service import TranslationService
from services.detection_service import DetectionService
from services.inpainting_service import InpaintingService
from services.render_service import RenderService
from services.export_service import ExportService
from services.page_analysis_service import PageAnalysisService
from services.bubble_analysis_service import BubbleAnalysisService
from services.layout_planner_service import LayoutPlannerService
from app.models import MangaPage
from app.version import APP_NAME

logger = logging.getLogger(APP_NAME)

# Services
translation_service = TranslationService()
detection_service = DetectionService()
inpainting_service = InpaintingService()
render_service = RenderService()
export_service = ExportService(render_service)
page_analysis_service = PageAnalysisService()
bubble_analysis_service = BubbleAnalysisService()
layout_planner_service = LayoutPlannerService()

# In-memory project state
class ProjectState:
    def __init__(self):
        self.pages: List[MangaPage] = []
        self.current_page_idx: int = -1
        self.revision: int = 0
        self.lock = RLock()

    def touch(self) -> int:
        with self.lock:
            self.revision += 1
            return self.revision

state = ProjectState()


class JobManager:
    _TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
    _MAX_TERMINAL_JOBS = 50
    _JOB_TTL_SECONDS = 3600

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._active_keys: dict[str, str] = {}
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vibecleaner-job")

    def _prune_locked(self) -> None:
        """Drop old/terminal jobs so _jobs doesn't grow unbounded. Caller holds _lock."""
        now = time.time()
        # Age-based eviction of finished jobs.
        for job_id in [
            jid for jid, j in self._jobs.items()
            if j["status"] in self._TERMINAL_STATES and now - j.get("updated_at", now) > self._JOB_TTL_SECONDS
        ]:
            self._jobs.pop(job_id, None)
        # Count-based cap on remaining finished jobs (keep most recent).
        terminal = [(jid, j) for jid, j in self._jobs.items() if j["status"] in self._TERMINAL_STATES]
        if len(terminal) > self._MAX_TERMINAL_JOBS:
            terminal.sort(key=lambda kv: kv[1].get("updated_at", 0))
            for job_id, _ in terminal[: len(terminal) - self._MAX_TERMINAL_JOBS]:
                self._jobs.pop(job_id, None)

    def start(
        self,
        kind: str,
        page_idx: int,
        key: str,
        worker: Callable[[dict[str, Any]], Any],
    ) -> dict[str, Any]:
        with self._lock:
            self._prune_locked()
            active_job_id = self._active_keys.get(key)
            if active_job_id:
                active_job = self._jobs.get(active_job_id)
                if active_job and active_job["status"] in {"queued", "running"}:
                    return self._public(active_job)

            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id,
                "kind": kind,
                "page_idx": page_idx,
                "key": key,
                "status": "queued",
                "progress": 0,
                "message": "Queued",
                "result": None,
                "error": None,
                "cancel_requested": False,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._jobs[job_id] = job
            self._active_keys[key] = job_id
            self._executor.submit(self._run, job_id, worker)
            return self._public(job)

    def _run(self, job_id: str, worker: Callable[[dict[str, Any]], Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job["cancel_requested"]:
                job["status"] = "cancelled"
                job["message"] = "Cancelled"
                job["updated_at"] = time.time()
                self._active_keys.pop(job["key"], None)
                return
            job["status"] = "running"
            job["progress"] = 5
            job["message"] = "Starting"
            job["updated_at"] = time.time()

        try:
            result = worker(job)
            with self._lock:
                if job["cancel_requested"]:
                    job["status"] = "cancelled"
                    job["message"] = "Cancelled"
                else:
                    job["status"] = "succeeded"
                    job["progress"] = 100
                    job["message"] = "Complete"
                    job["result"] = result
                job["updated_at"] = time.time()
        except Exception as exc:
            logger.exception("Background job failed: %s", job_id)
            with self._lock:
                if job["cancel_requested"]:
                    job["status"] = "cancelled"
                    job["message"] = "Cancelled"
                else:
                    job["status"] = "failed"
                    job["error"] = str(exc)
                    job["message"] = "Failed"
                job["updated_at"] = time.time()
        finally:
            with self._lock:
                self._active_keys.pop(self._jobs[job_id]["key"], None)

    def update(self, job: dict[str, Any], *, progress: int | None = None, message: str | None = None) -> None:
        with self._lock:
            if progress is not None:
                job["progress"] = max(0, min(100, progress))
            if message is not None:
                job["message"] = message
            job["updated_at"] = time.time()

    def ensure_not_cancelled(self, job: dict[str, Any]) -> None:
        if job.get("cancel_requested"):
            raise RuntimeError("Job was cancelled")

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._public(job) if job else None

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job["status"] in {"queued", "running"}:
                job["cancel_requested"] = True
                job["message"] = "Cancellation requested"
                job["updated_at"] = time.time()
            return self._public(job)

    def _public(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": job["job_id"],
            "kind": job["kind"],
            "page_idx": job["page_idx"],
            "status": job["status"],
            "progress": job["progress"],
            "message": job["message"],
            "result": job["result"],
            "error": job["error"],
        }


job_manager = JobManager()
cache_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vibecleaner-cache")


def submit_cache_task(worker: Callable[[], None]) -> None:
    cache_executor.submit(worker)


THUMBNAIL_WIDTH = 150
PREVIEW_MAX_DIMENSION = 1600
JPEG_QUALITY = 90


def encode_png_bytes(image: np.ndarray) -> bytes:
    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Failed to encode image")
    return buffer.tobytes()


def encode_jpeg_bytes(image: np.ndarray, quality: int = JPEG_QUALITY) -> bytes:
    success, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        raise ValueError("Failed to encode image")
    return buffer.tobytes()


def encode_resized_png_bytes(image: np.ndarray, max_dimension: int) -> bytes:
    height, width = image.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions")

    scale = min(max_dimension / max(width, height), 1.0)
    if scale < 1.0:
        target_width = max(1, int(width * scale))
        target_height = max(1, int(height * scale))
        image = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return encode_png_bytes(image)


def encode_resized_jpeg_bytes(image: np.ndarray, max_dimension: int, quality: int = JPEG_QUALITY) -> bytes:
    height, width = image.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions")

    scale = min(max_dimension / max(width, height), 1.0)
    if scale < 1.0:
        target_width = max(1, int(width * scale))
        target_height = max(1, int(height * scale))
        image = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return encode_jpeg_bytes(image, quality=quality)


def encode_thumbnail_bytes(image: np.ndarray) -> bytes:
    return encode_resized_png_bytes(image, THUMBNAIL_WIDTH)


def encode_preview_bytes(image: np.ndarray) -> bytes:
    return encode_resized_png_bytes(image, PREVIEW_MAX_DIMENSION)


def encode_preview_jpeg_bytes(image: np.ndarray) -> bytes:
    return encode_resized_jpeg_bytes(image, PREVIEW_MAX_DIMENSION)


def load_cv_image(file_path: str) -> np.ndarray | None:
    """Load an image from disk without relying on OpenCV's path handling."""
    try:
        data = np.fromfile(file_path, dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def ensure_original_thumbnail(page: MangaPage) -> bytes:
    cached = getattr(page, "_thumbnail_original_bytes", None)
    if cached is not None:
        return cached

    if getattr(page, "_loaded", True) is False and page.file_path:
        img = load_cv_image(page.file_path)
        if img is None:
            logger.error("Failed to load image for thumbnail: %s", page.file_path)
            raise HTTPException(status_code=500, detail="Failed to load page image")
    else:
        ensure_page_image(page)
        img = page.cv_image

    thumb_bytes = encode_thumbnail_bytes(img)
    page._thumbnail_original_bytes = thumb_bytes
    return thumb_bytes


def warm_original_thumbnail(page: MangaPage) -> None:
    try:
        ensure_original_thumbnail(page)
    except Exception as exc:
        logger.warning("Failed to generate thumbnail for %s: %s", page.file_path, exc)


def invalidate_page_caches(
    page: MangaPage,
    *,
    thumbnails: bool = False,
    layouts: bool = True,
    responses: bool = False,
) -> None:
    if layouts:
        page._bubble_layout_cache = {}
    if thumbnails:
        for attr in ("_thumbnail_original_bytes", "_thumbnail_inpainted_bytes"):
            if hasattr(page, attr):
                delattr(page, attr)
    if responses:
        for attr in (
            "_original_response_bytes",
            "_inpainted_response_bytes",
            "_preview_original_bytes",
            "_preview_inpainted_bytes",
        ):
            if hasattr(page, attr):
                delattr(page, attr)

def ensure_page_image(page: MangaPage) -> None:
    if getattr(page, "_loaded", True) is False or page.cv_image is None or page.cv_image.size == 0:
        cv_img = load_cv_image(page.file_path)
        if cv_img is None:
            logger.error("Failed to load page image: %s", page.file_path)
            raise HTTPException(status_code=500, detail="Failed to load page image")
        page.cv_image = cv_img
        page._width = cv_img.shape[1]
        page._height = cv_img.shape[0]
        page._loaded = True
