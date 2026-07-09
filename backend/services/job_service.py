import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from typing import Any, Callable

from core.version import APP_NAME


logger = logging.getLogger(APP_NAME)


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
        for job_id in [
            jid for jid, j in self._jobs.items()
            if j["status"] in self._TERMINAL_STATES and now - j.get("updated_at", now) > self._JOB_TTL_SECONDS
        ]:
            self._jobs.pop(job_id, None)

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
