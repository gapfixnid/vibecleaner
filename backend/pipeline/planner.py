from __future__ import annotations

from .plan import PipelinePlan


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