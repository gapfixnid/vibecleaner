import json

from fastapi.testclient import TestClient
from PIL import Image

from backend.api.routes.project import _append_imported_pages
from backend.core.models import MangaPage
from backend.core.state.project_state import ProjectState
from backend.main import create_app


TEST_TOKEN = "BwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc"


def _page(path: str) -> MangaPage:
    return MangaPage(file_path=path)


def test_first_image_import_selects_the_new_page_immediately():
    state = ProjectState()

    result = _append_imported_pages(state, [_page("first.png")])

    assert result == {"page_count": 1, "current_index": 0, "added": 1}
    assert state.current_page_idx == 0


def test_single_image_append_selects_its_new_index():
    state = ProjectState()
    state.pages = [_page("existing.png")]
    state.current_page_idx = 0

    result = _append_imported_pages(state, [_page("new.png")])

    assert result == {"page_count": 2, "current_index": 1, "added": 1}
    assert state.current_page_idx == 1


def test_multi_image_append_preserves_existing_selection():
    state = ProjectState()
    state.pages = [_page("existing.png")]
    state.current_page_idx = 0

    result = _append_imported_pages(state, [_page("two.png"), _page("three.png")])

    assert result == {"page_count": 3, "current_index": 0, "added": 2}
    assert state.current_page_idx == 0


def test_open_files_exposes_the_first_import_without_waiting_for_a_second(tmp_path):
    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    Image.new("RGB", (32, 24), "white").save(first_path)
    Image.new("RGB", (40, 30), "white").save(second_path)
    headers = {"X-VibeCleaner-Token": TEST_TOKEN}

    with TestClient(create_app(TEST_TOKEN)) as client:
        first = client.post(
            "/api/project/open-files",
            data={"files_json": json.dumps([str(first_path)])},
            headers=headers,
        )
        after_first = client.get("/api/pages", headers=headers)
        second = client.post(
            "/api/project/open-files",
            data={"files_json": json.dumps([str(second_path)])},
            headers=headers,
        )

    assert first.status_code == 200
    assert first.json()["current_index"] == 0
    assert [page["filename"] for page in first.json()["pages"]] == ["first.png"]
    assert after_first.json()["current_index"] == 0
    assert [page["filename"] for page in after_first.json()["pages"]] == ["first.png"]
    assert second.json()["current_index"] == 1
    assert [page["filename"] for page in second.json()["pages"]] == ["first.png", "second.png"]


def test_open_files_reports_corrupt_images_instead_of_silently_skipping(tmp_path):
    broken_path = tmp_path / "broken.png"
    broken_path.write_bytes(b"not an image")
    headers = {"X-VibeCleaner-Token": TEST_TOKEN}

    with TestClient(create_app(TEST_TOKEN)) as client:
        response = client.post(
            "/api/project/open-files",
            data={"files_json": json.dumps([str(broken_path)])},
            headers=headers,
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "NO_IMPORTABLE_IMAGES"
    assert detail["import_report"]["rejected"][0]["code"] == "IMAGE_DECODE_FAILED"
