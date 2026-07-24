from backend.pipeline.planner import PipelinePlanner
from backend.pipeline.resources import ResourceClass


def test_v2_page_plan_declares_stage_resources_and_dependencies():
    plan = PipelinePlanner().translate_page_dag_plan()
    plan.validate()
    assert [stage.name for stage in plan.stages] == [
        "detection", "ocr", "translation", "inpainting", "layout", "rendering"
    ]
    assert plan.stages[0].resource is ResourceClass.GPU
    assert plan.stages[2].resource is ResourceClass.NETWORK
    assert plan.stages[2].parallel_safe is False
    assert plan.stages[3].depends_on == ("ocr",)
    assert plan.stages[4].depends_on == ("translation", "inpainting")
    assert plan.stages[-1].depends_on == ("layout",)
