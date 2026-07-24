import time

from backend.infrastructure.jobs import JobManager
from backend.pipeline.checkpoint import CheckpointManifest, JsonCheckpointStore
from backend.pipeline.telemetry import JsonlTelemetrySink, PipelineTelemetryRecord, load_telemetry


def test_job_failure_exposes_structured_error_fields():
    manager = JobManager()
    job = manager.start("test", 0, "structured-error", lambda _job: (_ for _ in ()).throw(ValueError("bad input")))
    deadline = time.time() + 2
    while time.time() < deadline:
        current = manager.get(job["job_id"])
        if current and current["status"] == "failed":
            break
        time.sleep(0.01)
    assert current["error_code"] == "JOB_FAILED"
    assert current["error"] == "bad input"


def test_checkpoint_manifest_exposes_contract_version(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    store.save(CheckpointManifest("run", "page", metadata={"pipeline_contract_version": "v2"}))
    assert store.load("run").contract_version == "v2"


def test_telemetry_prune_rewrite_is_readable(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    sink = JsonlTelemetrySink(path, max_bytes=1024)
    sink.record(PipelineTelemetryRecord(2, "run", "page", True))
    assert len(load_telemetry(path)) == 1
