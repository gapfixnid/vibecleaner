from backend.pipeline.checkpoint import CheckpointManifest, JsonCheckpointStore


def test_checkpoint_store_round_trips_manifest_atomically(tmp_path):
    store = JsonCheckpointStore(tmp_path / "checkpoints")
    manifest = CheckpointManifest(
        run_id="run-1", page_id="page-1", completed_stages=["detection", "ocr"],
        artifact_keys=["detection_result"], metadata={"version": 2}
    )
    store.save(manifest)
    assert store.load("run-1") == manifest
    store.delete("run-1")
    assert store.load("run-1") is None
