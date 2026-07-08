import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class BackendQtRuntimeTests(unittest.TestCase):
    def test_create_app_initializes_qapplication_for_layout_metrics(self):
        from main import create_app

        create_app()

        self.assertIsNotNone(QApplication.instance())


if __name__ == "__main__":
    unittest.main()
