from core.models.image import ImageData
from core.models.page import MangaPage
from pipeline.context import PipelineContext
from pipeline.plan import PipelinePlan
from pipeline.registry import StageRegistry
from pipeline.runner import PipelineRunner
from pipeline.validation.results import PipelineValidationError, ValidationIssue


class RecordingStage:
    name = "record"

    def run(self, context):
        context.artifacts["recorded"] = True
        return context


class FailingStage:
    name = "fail"

    def run(self, context):
        raise PipelineValidationError(
            [ValidationIssue(code="missing_input", severity="error", message="input missing", stage=self.name)]
        )


def make_context():
    return PipelineContext(
        page_id="page-1",
        page=MangaPage(file_path="C:/tmp/page.png", page_id="page-1"),
        image=ImageData(array=None, explicit_width=1, explicit_height=1),
        settings={},
    )


def test_runner_executes_stage_and_records_provenance():
    registry = StageRegistry()
    registry.register(RecordingStage())
    runner = PipelineRunner(registry=registry)

    result = runner.run(make_context(), PipelinePlan(stages=["record"]))

    assert result.succeeded
    assert result.context.artifacts["recorded"] is True
    assert result.context.provenance.stages[0].stage == "record"
    assert result.context.provenance.stages[0].output_summary == {"artifact_count": 1}


def test_runner_stops_on_validation_error():
    registry = StageRegistry()
    registry.register(FailingStage())
    runner = PipelineRunner(registry=registry)

    result = runner.run(make_context(), PipelinePlan(stages=["fail"]))

    assert not result.succeeded
    assert result.issues[0].code == "missing_input"
    assert result.context.provenance.stages[0].errors == ["input missing"]
