from __future__ import annotations

from .plan import PipelinePlan
from .dag import DagPipelinePlan, DagStage
from .resources import ResourceClass


class PipelinePlanner:
    def translate_page_plan(self) -> PipelinePlan:
        return PipelinePlan(
            stages=[
                "detection",
                "ocr",
                "translation",
                "inpainting",
                "layout",
                "rendering",
            ]
        )

    def translate_page_dag_plan(self) -> DagPipelinePlan:
        """Return the v2 plan while keeping the v1 stage ordering unchanged."""
        return DagPipelinePlan(
            stages=(
                DagStage("detection", resource=ResourceClass.GPU),
                DagStage("ocr", ("detection",), ResourceClass.CPU),
                DagStage("translation", ("ocr",), ResourceClass.NETWORK),
                DagStage("inpainting", ("translation",), ResourceClass.GPU),
                DagStage("layout", ("inpainting",), ResourceClass.CPU),
                DagStage("rendering", ("layout",), ResourceClass.IO),
            )
        )
