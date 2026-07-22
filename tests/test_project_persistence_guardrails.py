import json
import zipfile
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException

from backend.api.routes import project as project_route
from backend.core.models import MangaPage
from backend.core.state.project_state import ProjectState
from backend.infrastructure.storage.project_schema import (
    CURRENT_PROJECT_SCHEMA_VERSION,
    ORIGINAL_PAGE_ID_EXTENSION,
    PROJECT_FORMAT,
)


def _container_with_page() -> SimpleNamespace:
    page = MangaPage(
        file_path="source.png",
        page_id="page-1",
        cv_image=np.zeros((8, 12, 3), dtype=np.uint8),
        bubbles=[],
        bubble_counter=0,
    )
    return SimpleNamespace(project_state=ProjectState(pages=[page], current_page_idx=0))


class DeferredCacheTasks:
    def submit(self, callback):
        return None


def test_project_save_writes_the_versioned_envelope(tmp_path):
    destination = tmp_path / "project.vibe"

    result = project_route.save_project(
        file_path=str(destination),
        selected_indices="[0]",
        container=_container_with_page(),
    )

    assert result == {"status": "ok"}
    with zipfile.ZipFile(destination, "r") as archive:
        metadata = json.loads(archive.read("project.json").decode("utf-8"))
    assert metadata["format"] == PROJECT_FORMAT
    assert metadata["schema_version"] == CURRENT_PROJECT_SCHEMA_VERSION
    assert metadata["app_version"] == "0.2.0"
    assert metadata["selected_indices"] == [0]
    assert metadata["pages"][0]["page_id"] == "page-1"


def test_failed_project_save_preserves_the_existing_file(tmp_path, monkeypatch):
    destination = tmp_path / "project.vibe"
    original_bytes = b"existing project bytes"
    destination.write_bytes(original_bytes)
    monkeypatch.setattr(project_route.cv2, "imencode", lambda *args, **kwargs: (False, None))

    with pytest.raises(HTTPException, match="Failed to encode original image"):
        project_route.save_project(
            file_path=str(destination),
            selected_indices="[]",
            container=_container_with_page(),
        )

    assert destination.read_bytes() == original_bytes
    assert list(tmp_path.glob(".vibecleaner-project-*.tmp")) == []


def test_load_save_round_trip_preserves_additive_extension_fields(tmp_path):
    source = tmp_path / "source.vibe"
    destination = tmp_path / "round-trip.vibe"
    success, encoded = project_route.cv2.imencode(".png", np.zeros((8, 12, 3), dtype=np.uint8))
    assert success
    metadata = {
        "format": PROJECT_FORMAT,
        "schema_version": CURRENT_PROJECT_SCHEMA_VERSION,
        "app_version": "future-minor",
        "version": "2.0",
        "current_index": 0,
        "selected_indices": [0],
        "future_project_field": {"keep": True},
        "pages": [
            {
                "file_name": "page_0_orig.png",
                "original_file_path": "source.png",
                "inpaint_file_name": None,
                "bubble_counter": 1,
                "display_name": "Page 1",
                "status": "ready_for_review",
                "problems": [],
                "future_page_field": [1, 2, 3],
                "bubbles": [
                    {
                        "id": 1,
                        "box": [1, 1, 6, 6],
                        "text": "hello",
                        "translated": "안녕",
                        "future_bubble_field": "keep",
                        "style": {"font_size": 14, "future_style_field": 42},
                        "layout_plan": {"future_layout_field": "keep"},
                    }
                ],
            }
        ],
    }
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(metadata))
        archive.writestr("images/page_0_orig.png", encoded.tobytes())

    container = SimpleNamespace(project_state=ProjectState(), cache_tasks=DeferredCacheTasks())
    project_route.load_project(file_path=str(source), container=container)
    project_route.save_project(file_path=str(destination), selected_indices="[0]", container=container)

    with zipfile.ZipFile(destination, "r") as archive:
        saved = json.loads(archive.read("project.json").decode("utf-8"))
    saved_page = saved["pages"][0]
    saved_bubble = saved_page["bubbles"][0]
    assert saved["future_project_field"] == {"keep": True}
    assert saved_page["future_page_field"] == [1, 2, 3]
    assert saved_bubble["future_bubble_field"] == "keep"
    assert saved_bubble["style"]["future_style_field"] == 42
    assert saved_bubble["layout_plan"]["future_layout_field"] == "keep"


def test_malicious_project_page_id_is_rekeyed_before_runtime_and_round_trip(tmp_path):
    source = tmp_path / "malicious.vibe"
    destination = tmp_path / "safe.vibe"
    success, encoded = project_route.cv2.imencode(".png", np.zeros((8, 12, 3), dtype=np.uint8))
    assert success
    metadata = {
        "format": PROJECT_FORMAT,
        "schema_version": CURRENT_PROJECT_SCHEMA_VERSION,
        "app_version": "external",
        "version": "2.0",
        "current_index": 0,
        "selected_indices": [0],
        "pages": [{
            "page_id": r"..\outside",
            "file_name": "page_0_orig.png",
            "original_file_path": "source.png",
            "inpaint_file_name": None,
            "bubbles": [],
        }],
    }
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(metadata))
        archive.writestr("images/page_0_orig.png", encoded.tobytes())

    container = SimpleNamespace(project_state=ProjectState(), cache_tasks=DeferredCacheTasks())
    project_route.load_project(file_path=str(source), container=container)
    loaded_page = container.project_state.pages[0]
    assert len(loaded_page.page_id) == 32
    assert loaded_page.project_extensions[ORIGINAL_PAGE_ID_EXTENSION] == r"..\outside"

    reopened = SimpleNamespace(project_state=ProjectState(), cache_tasks=DeferredCacheTasks())
    project_route.load_project(file_path=str(source), container=reopened)
    assert reopened.project_state.pages[0].page_id == loaded_page.page_id

    project_route.save_project(file_path=str(destination), selected_indices="[0]", container=container)
    with zipfile.ZipFile(destination, "r") as archive:
        saved_page = json.loads(archive.read("project.json"))["pages"][0]
    assert saved_page["page_id"] == loaded_page.page_id
    assert saved_page[ORIGINAL_PAGE_ID_EXTENSION] == r"..\outside"
