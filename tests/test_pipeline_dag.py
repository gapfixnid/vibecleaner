from types import SimpleNamespace
import threading
from time import sleep

import pytest

from backend.pipeline.dag import DagPipelineExecutor, DagPipelinePlan, DagStage
from backend.pipeline.checkpoint import CheckpointManifest, JsonCheckpointStore
from backend.pipeline.registry import StageRegistry
from backend.pipeline.provenance import ProvenanceTrace
from backend.pipeline.resources import ResourceClass
from backend.pipeline.context import StageOutput


class Stage:
    def __init__(self, name, marker):
        self.name = name
        self.marker = marker

    def run(self, context):
        context.artifacts.setdefault("order", []).append(self.marker)
        return context


def test_dag_respects_dependencies_and_allows_independent_nodes():
    registry = StageRegistry()
    for name in ("detect", "ocr", "translate"):
        registry.register(Stage(name, name))
    context = SimpleNamespace(artifacts={}, provenance=SimpleNamespace())
    # Use the real provenance object expected by the executor.
    context.provenance = ProvenanceTrace()
    plan = DagPipelinePlan((DagStage("ocr", ("detect",)), DagStage("detect"), DagStage("translate", ("ocr",))))
    result = DagPipelineExecutor(registry).run(context, plan)
    assert result.succeeded
    assert context.artifacts["order"] == ["detect", "ocr", "translate"]


def test_dag_rejects_cycles():
    with pytest.raises(ValueError, match="cycle"):
        DagPipelinePlan((DagStage("a", ("b",)), DagStage("b", ("a",)))).validate()


def test_dag_writes_stage_checkpoint(tmp_path):
    registry = StageRegistry()
    registry.register(Stage("detect", "detect"))
    context = SimpleNamespace(artifacts={}, provenance=ProvenanceTrace(), page_id="page-1")
    store = JsonCheckpointStore(tmp_path)
    result = DagPipelineExecutor(registry, checkpoint_store=store).run(
        context, DagPipelinePlan((DagStage("detect"),))
    )
    assert result.succeeded
    manifest = store.load(context.provenance.run_id)
    assert manifest is not None
    assert manifest.completed_stages == ["detect"]


def test_dag_resume_skips_stage_when_checkpoint_artifacts_are_hydrated():
    registry = StageRegistry()
    registry.register(Stage("detect", "detect"))
    context = SimpleNamespace(artifacts={"order": ["hydrated"]}, provenance=ProvenanceTrace(), page_id="page-1")
    manifest = CheckpointManifest(
        run_id="old-run", page_id="page-1", completed_stages=["detect"], artifact_keys=["order"]
    )
    result = DagPipelineExecutor(registry).run(
        context, DagPipelinePlan((DagStage("detect"),)), resume_manifest=manifest
    )
    assert result.succeeded
    assert context.artifacts["order"] == ["hydrated"]


def test_dag_resume_hydrates_page_artifacts_from_checkpoint_payload(tmp_path):
    registry = StageRegistry()
    registry.register(Stage("detect", "detect"))
    store = JsonCheckpointStore(tmp_path)
    first = SimpleNamespace(artifacts={}, provenance=ProvenanceTrace(), page_id="page-1")
    assert DagPipelineExecutor(registry, checkpoint_store=store).run(
        first, DagPipelinePlan((DagStage("detect"),))
    ).succeeded
    manifest = store.load(first.provenance.run_id)

    resumed = SimpleNamespace(artifacts={}, provenance=ProvenanceTrace(), page_id="page-1")
    result = DagPipelineExecutor(registry, checkpoint_store=store).run(
        resumed, DagPipelinePlan((DagStage("detect"),)), resume_manifest=manifest
    )
    assert result.succeeded
    assert resumed.artifacts["order"] == ["detect"]
    assert store.payload_path_for(first.provenance.run_id).exists()


def test_dag_does_not_resume_when_visual_revision_changes():
    registry = StageRegistry()
    registry.register(Stage("detect", "detect"))
    context = SimpleNamespace(
        artifacts={"order": ["hydrated"], "visual_revision": 2},
        provenance=ProvenanceTrace(), page_id="page-1",
    )
    manifest = CheckpointManifest(
        run_id="old-run", page_id="page-1", completed_stages=["detect"],
        artifact_keys=["order"], metadata={"visual_revision": 1},
    )
    result = DagPipelineExecutor(registry).run(
        context, DagPipelinePlan((DagStage("detect"),)), resume_manifest=manifest
    )
    assert result.succeeded
    assert context.artifacts["order"] == ["hydrated", "detect"]


def test_checkpoint_round_trips_stage_output_and_resume_keeps_live_page_identity(tmp_path):
    registry = StageRegistry()

    class OutputStage(Stage):
        def run(self, context):
            context.artifacts["translation_output"] = StageOutput("translation", {"text": "ok"})
            return context

    registry.register(OutputStage("translate", "translate"))
    store = JsonCheckpointStore(tmp_path)
    live_page = object()
    first = SimpleNamespace(
        artifacts={"snapshot_page": live_page, "project_generation": 1, "visual_revision": 2, "image_visual_revision": 3, "config": None},
        provenance=ProvenanceTrace(), page_id="page-1",
    )
    assert DagPipelineExecutor(registry, checkpoint_store=store).run(
        first, DagPipelinePlan((DagStage("translate"),))
    ).succeeded
    manifest = store.load(first.provenance.run_id)
    resumed = SimpleNamespace(
        artifacts={"snapshot_page": live_page, "project_generation": 1, "visual_revision": 2, "image_visual_revision": 3, "config": None},
        provenance=ProvenanceTrace(), page_id="page-1",
    )
    result = DagPipelineExecutor(registry, checkpoint_store=store).run(
        resumed, DagPipelinePlan((DagStage("translate"),)), resume_manifest=manifest
    )
    assert result.succeeded
    assert isinstance(resumed.artifacts["translation_output"], StageOutput)
    assert resumed.artifacts["snapshot_page"] is live_page


def test_dag_retries_transient_stage_failure():
    class Flaky(Stage):
        def __init__(self):
            super().__init__("detect", "detect")
            self.attempts = 0

        def run(self, context):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("transient")
            return super().run(context)

    registry = StageRegistry()
    stage = Flaky()
    registry.register(stage)
    context = SimpleNamespace(artifacts={}, provenance=ProvenanceTrace(), page_id="page-1")
    result = DagPipelineExecutor(registry, retry_backoff_seconds=0).run(
        context, DagPipelinePlan((DagStage("detect", max_retries=1),))
    )
    assert result.succeeded
    assert stage.attempts == 2


def test_dag_runs_parallel_safe_independent_stages_concurrently():
    barrier = threading.Barrier(2, timeout=1)

    class ConcurrentStage(Stage):
        def run(self, context):
            barrier.wait()
            context.artifacts[self.name] = True
            return context

    registry = StageRegistry()
    registry.register(ConcurrentStage("translate", "translate"))
    registry.register(ConcurrentStage("inpaint", "inpaint"))
    context = SimpleNamespace(artifacts={}, provenance=ProvenanceTrace(), page_id="page-1")
    plan = DagPipelinePlan((
        DagStage("translate", resource=ResourceClass.NETWORK, parallel_safe=True),
        DagStage("inpaint", resource=ResourceClass.GPU, parallel_safe=True),
    ))
    result = DagPipelineExecutor(registry).run(context, plan)
    assert result.succeeded
    assert context.artifacts == {"translate": True, "inpaint": True}


def test_parallel_stage_duration_uses_worker_completion_time():
    registry = StageRegistry()
    registry.register(DelayStage("slow", 0.04))
    registry.register(DelayStage("fast", 0.01))
    context = SimpleNamespace(artifacts={}, provenance=ProvenanceTrace(), page_id="page-1")
    result = DagPipelineExecutor(registry).run(context, DagPipelinePlan((
        DagStage("slow", resource=ResourceClass.NETWORK, parallel_safe=True),
        DagStage("fast", resource=ResourceClass.GPU, parallel_safe=True),
    )))
    assert result.succeeded
    durations = {stage.stage: stage.duration_ms for stage in context.provenance.stages}
    assert durations["slow"] >= 30
    assert durations["fast"] < durations["slow"]


class DelayStage(Stage):
    def __init__(self, name, delay):
        super().__init__(name, name)
        self.delay = delay

    def run(self, context):
        sleep(self.delay)
        context.artifacts[self.name] = True
        return context
