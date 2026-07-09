from backend.core.models.geometry import Box
from backend.core.models.image import ImageData
from backend.core.state.project_state import ProjectState
from backend.core.state.repository import InMemoryProjectRepository


def test_box_clamps_to_image_bounds():
    box = Box(x1=-10, y1=5, x2=120, y2=90)

    assert box.clamp(width=100, height=80) == Box(x1=0, y1=5, x2=100, y2=80)


def test_box_rejects_empty_geometry():
    box = Box(x1=5, y1=5, x2=5, y2=7)

    assert not box.is_valid()


def test_image_data_reports_dimensions_from_array():
    class FakeArray:
        shape = (24, 32, 3)

    image = ImageData(array=FakeArray(), mode="RGB")

    assert image.width == 32
    assert image.height == 24


def test_repository_returns_page_by_id():
    state = ProjectState()
    repo = InMemoryProjectRepository(state)

    page = repo.create_page(file_path="C:/tmp/page.png", display_name="page-1")

    assert repo.get_page(page.page_id).page_id == page.page_id
    assert repo.list_pages() == [page]
