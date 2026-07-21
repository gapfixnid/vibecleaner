import threading
import unittest
from unittest.mock import patch

from backend.api.use_cases import page_images
from backend.core.models import MangaPage
from backend.core.state.project_state import ProjectState


class PageImageResponseTests(unittest.TestCase):
    def test_original_thumbnail_is_generated_outside_project_lock(self):
        state = ProjectState()
        page = MangaPage(file_path="sample.png", cv_image=None)
        page.page_id = "page_a"
        page._loaded = False
        with state.lock:
            state.pages = [page]

        lock_was_available = []

        def generate_thumbnail(_page):
            def acquire_from_other_thread():
                acquired = state.lock.acquire(timeout=0.2)
                lock_was_available.append(acquired)
                if acquired:
                    state.lock.release()

            worker = threading.Thread(target=acquire_from_other_thread)
            worker.start()
            worker.join()
            return b"thumbnail"

        with patch.object(page_images, "ensure_original_thumbnail", side_effect=generate_thumbnail):
            response = page_images.get_page_image_response(state, "page_a", thumbnail=True)

        self.assertEqual(lock_was_available, [True])
        self.assertEqual(response.media_type, "image/png")


if __name__ == "__main__":
    unittest.main()
