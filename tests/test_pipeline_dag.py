from types import SimpleNamespace

import pytest

from backend.pipeline.dag import DagPipelineExecutor, DagPipelinePlan, DagStage
from backend.pipeline.checkpoint import JsonCheckpointStore
from backend.pipeline.registry import StageRegistry
from backend.pipeline.provenance import ProvenanceTrace


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
