import asyncio
import unittest
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

TEST_TOKEN = "BwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc"

class BackendQtRuntimeTests(unittest.TestCase):
    def test_create_app_initializes_qapplication_for_layout_metrics(self):
        from backend.main import create_app

        create_app(TEST_TOKEN)

        self.assertIsNotNone(QApplication.instance())

    def test_lifespan_flushes_detection_ocr_cache(self):
        from backend.main import lifespan

        detection_service = SimpleNamespace(shutdown_called=False)

        def shutdown():
            detection_service.shutdown_called = True

        detection_service.shutdown = shutdown
        app = SimpleNamespace(
            state=SimpleNamespace(
                container=SimpleNamespace(detection_service=detection_service)
            )
        )

        async def run_lifespan():
            async with lifespan(app):
                pass

        asyncio.run(run_lifespan())

        self.assertTrue(detection_service.shutdown_called)

if __name__ == "__main__":
    unittest.main()
