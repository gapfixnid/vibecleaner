from __future__ import annotations

from typing import Protocol

from pipeline.context import PipelineContext


class Stage(Protocol):
    name: str

    def run(self, context: PipelineContext) -> PipelineContext:
        ...


class StageRegistry:
    def __init__(self) -> None:
        self._stages: dict[str, Stage] = {}

    def register(self, stage: Stage) -> None:
        self._stages[stage.name] = stage

    def get(self, name: str) -> Stage:
        try:
            return self._stages[name]
        except KeyError as exc:
            raise KeyError(f"Pipeline stage not registered: {name}") from exc
