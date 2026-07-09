import unittest
import sys
from pathlib import Path

from core.models import Rect

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.models import MangaPage, TextBubble
from services.review_state_service import derive_bubble_status, derive_page_status, refresh_page_status


class ReviewStateTests(unittest.TestCase):
    def test_bubble_review_state_survives_project_roundtrip(self):
        bubble = TextBubble(
            id=1,
            box=Rect(1, 2, 30, 40),
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
                    box=Rect(0, 0, 10, 10),
                    text="hello",
                    translated="안녕",
                )
            ],
        )

        refresh_page_status(page)

        self.assertEqual(derive_bubble_status(page.bubbles[0]), "ok")
        self.assertEqual(derive_page_status(page), "ready_for_review")

    def test_page_review_state_survives_project_roundtrip(self):
        page = MangaPage(
            file_path="sample.png",
            cv_image=None,
            status="has_warnings",
            problems=["layout overflow"],
            bubbles=[
                TextBubble(
                    id=1,
                    box=Rect(0, 0, 10, 10),
                    text="hello",
                    translated="안녕",
                    status="needs_review",
                    problems=["manual check"],
                    edited=True,
                )
            ],
        )

        restored = MangaPage.from_project_dict(page.to_project_dict(), cv_image=None)

        self.assertEqual(restored.status, "has_warnings")
        self.assertEqual(restored.problems, ["layout overflow"])
        self.assertEqual(restored.bubbles[0].status, "needs_review")
        self.assertEqual(restored.bubbles[0].problems, ["manual check"])
        self.assertTrue(restored.bubbles[0].edited)


if __name__ == "__main__":
    unittest.main()
