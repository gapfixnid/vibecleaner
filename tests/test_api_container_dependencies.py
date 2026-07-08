from types import SimpleNamespace

from api.routes.pages import run_translate_all
from main import create_app
from pipeline.plan import PipelinePlan


def test_app_exposes_container_and_settings_route():
    app = create_app()

    assert hasattr(app.state, "container")
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            route_paths.update(child.path for child in original_router.routes if hasattr(child, "path"))
    assert "/api/settings" in route_paths


class _Lock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _RecordingJobManager:
    def __init__(self):
        self.result = None

    def start(self, kind, page_idx, key, work):
        job = {"cancel_requested": False}
        self.result = work(job)
        return {"kind": kind, "page_idx": page_idx, "key": key, "result": self.result}


class _RecordingRunner:
    def __init__(self):
        self.plan = None
        self.context = None

    def run(self, context, plan):
        self.context = context
        self.plan = plan
        context.artifacts["result"] = {"translated_count": 1}
        return SimpleNamespace(succeeded=True, context=context, issues=[])


class _Planner:
    def translate_page_plan(self):
        return PipelinePlan(stages=["detection", "ocr", "translation", "inpainting", "layout", "rendering"])


def test_translate_all_uses_canonical_pipeline_runner():
    page = SimpleNamespace(page_id="page_a")
    state = SimpleNamespace(lock=_Lock(), pages=[page])
    runner = _RecordingRunner()
    container = SimpleNamespace(
        legacy_state=state,
        config=SimpleNamespace(source_language="Japanese", target_language="Korean"),
        job_manager=_RecordingJobManager(),
        pipeline_runner=runner,
        pipeline_planner=_Planner(),
    )

    response = run_translate_all("page_a", container=container)

    assert response["result"] == {"translated_count": 1}
    assert runner.plan.stages == ["detection", "ocr", "translation", "inpainting", "layout", "rendering"]
    assert runner.context.page_id == "page_a"
