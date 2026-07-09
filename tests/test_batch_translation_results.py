import time
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.routes.pages import _run_translate_batch_pages
from backend.infrastructure.jobs import JobManager


class _Lock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _RecordingJobManager:
    def __init__(self):
        self.updates = []

    def update(self, job, *, progress=None, message=None):
        self.updates.append({"progress": progress, "message": message})

    def ensure_not_cancelled(self, job):
        if job.get("cancel_requested"):
            raise RuntimeError("Job was cancelled")


def _container():
    pages = [
        SimpleNamespace(page_id="page-a"),
        SimpleNamespace(page_id="page-b"),
        SimpleNamespace(page_id="page-c"),
    ]
    return SimpleNamespace(
        project_state=SimpleNamespace(lock=_Lock(), pages=pages),
        config=SimpleNamespace(ui_language="English"),
        job_manager=_RecordingJobManager(),
        pipeline_runner=SimpleNamespace(),
        pipeline_planner=SimpleNamespace(),
    )


def test_batch_translation_reports_successes_and_page_scoped_failures():
    container = _container()
    job = {"cancel_requested": False}

    with patch(
        "backend.api.routes.pages.run_page_translation",
        side_effect=[
            {"translated_count": 1},
            HTTPException(status_code=500, detail="OCR failed"),
            RuntimeError("Inpainting failed"),
        ],
    ):
        result = _run_translate_batch_pages(job, ["page-a", "page-b", "page-c"], container)

    assert result == {
        "status": "succeeded_with_errors",
        "successful_pages": 1,
        "total_pages": 3,
        "successful_page_indices": [0],
        "failed_pages": [
            {"page_id": "page-b", "page_idx": 1, "error": "OCR failed"},
            {"page_id": "page-c", "page_idx": 2, "error": "Inpainting failed"},
        ],
    }
    assert "translated_pages" not in result


def test_job_manager_preserves_succeeded_with_errors_worker_status():
    manager = JobManager()
    started = manager.start(
        kind="page-translation-batch",
        page_idx=0,
        key="batch-status-test",
        worker=lambda job: {"status": "succeeded_with_errors", "failed_pages": [{"page_id": "page-b"}]},
    )

    deadline = time.monotonic() + 1
    result = manager.get(started["job_id"])
    while result and result["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        result = manager.get(started["job_id"])

    assert result is not None
    assert result["status"] == "succeeded_with_errors"
    assert result["result"]["failed_pages"] == [{"page_id": "page-b"}]


def test_job_manager_preserves_failed_worker_status():
    manager = JobManager()
    started = manager.start(
        kind="page-translation-batch",
        page_idx=0,
        key="batch-failure-status-test",
        worker=lambda job: {"status": "failed", "failed_pages": [{"page_id": "page-a", "error": "OCR failed"}]},
    )

    deadline = time.monotonic() + 1
    result = manager.get(started["job_id"])
    while result and result["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        result = manager.get(started["job_id"])

    assert result is not None
    assert result["status"] == "failed"
    assert result["result"]["failed_pages"] == [{"page_id": "page-a", "error": "OCR failed"}]
    assert result["error"] == "page-a: OCR failed"


def test_batch_translation_marks_job_failed_when_every_page_fails():
    container = _container()
    job = {"cancel_requested": False}

    with patch(
        "backend.api.routes.pages.run_page_translation",
        side_effect=[HTTPException(status_code=500, detail="OCR failed")] * 3,
    ):
        result = _run_translate_batch_pages(job, ["page-a", "page-b", "page-c"], container)

    assert result["status"] == "failed"
    assert result["successful_pages"] == 0
    assert [page["page_id"] for page in result["failed_pages"]] == ["page-a", "page-b", "page-c"]
