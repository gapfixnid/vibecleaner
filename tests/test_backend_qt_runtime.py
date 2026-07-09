import unittest
from PySide6.QtWidgets import QApplication

class BackendQtRuntimeTests(unittest.TestCase):
    def test_create_app_initializes_qapplication_for_layout_metrics(self):
        from backend.main import create_app

        create_app()

        self.assertIsNotNone(QApplication.instance())

if __name__ == "__main__":
    unittest.main()
