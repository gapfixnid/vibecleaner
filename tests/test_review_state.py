import unittest
import sys
from pathlib import Path

from PySide6.QtCore import QRectF

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models import MangaPage, TextBubble
from services.review_state_service import derive_bubble_status, derive_page_status, refresh_page_status


class ReviewStateTests(unittest.TestCase):
    def test_bubble_review_state_survives_project_roundtrip(self):
        bubble = TextBubble(
            id=1,
            box=QRectF(1, 2, 30, 40),
            text="hello",
            translated="안녕",
            status="edited",
            problems=["manual adjustment"],
            edited=True,
        )

        restored = TextBubble.from_project_dict(bubble.to_project_dict())

        self.assertEqual(restored.status, "edited")
        self.assertEqual(restored.problems, ["manual adjustment"])
        self.assertTrue(restored.edited)

    def test_page_status_is_ready_for_review_when_typeset(self):
        page = MangaPage(
            file_path="sample.png",
            cv_image=None,
            inpainted_image=object(),
            bubbles=[
                TextBubble(
                    id=1,
                    box=QRectF(0, 0, 10, 10),
                    text="hello",
                    translated="안녕",
                )
            ],
        )

        refresh_page_status(page)

        self.assertEqual(derive_bubble_status(page.bubbles[0]), "ok")
        self.assertEqual(derive_page_status(page), "ready_for_review")


if __name__ == "__main__":
    unittest.main()
